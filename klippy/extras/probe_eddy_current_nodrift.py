# Support for eddy current based Z probes with internal temperature drift compensation
#
# Merged from:
# - probe_eddy_current.py: Copyright (C) 2021-2024 Kevin O'Connor
# - temperature_probe.py: Copyright (C) 2024 Eric Callahan
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging, math, bisect
import mcu
from . import ldc1612, probe, manual_probe

OUT_OF_RANGE = 99.9
KELVIN_TO_CELSIUS = -273.15
DRIFT_SAMPLE_COUNT = 9

######################################################################
# Polynomial Helper Classes and Functions
######################################################################

def calc_determinant(matrix):
    m = matrix
    aei = m[0][0] * m[1][1] * m[2][2]
    bfg = m[1][0] * m[2][1] * m[0][2]
    cdh = m[2][0] * m[0][1] * m[1][2]
    ceg = m[2][0] * m[1][1] * m[0][2]
    bdi = m[1][0] * m[0][1] * m[2][2]
    afh = m[0][0] * m[2][1] * m[1][2]
    return aei + bfg + cdh - ceg - bdi - afh


class Polynomial2d:
    def __init__(self, a, b, c):
        self.a = a
        self.b = b
        self.c = c

    def __call__(self, xval):
        return self.c * xval * xval + self.b * xval + self.a

    def get_coefs(self):
        return (self.a, self.b, self.c)

    def __str__(self):
        return "%f, %f, %f" % (self.a, self.b, self.c)

    def __repr__(self):
        parts = ["y(x) ="]
        deg = 2
        for i, coef in enumerate((self.c, self.b, self.a)):
            if round(coef, 8) == int(coef):
                coef = int(coef)
            if abs(coef) < 1e-10:
                continue
            cur_deg = deg - i
            x_str = "x^%d" % (cur_deg,) if cur_deg > 1 else "x" * cur_deg
            if len(parts) == 1:
                parts.append("%f%s" % (coef, x_str))
            else:
                sym = "-" if coef < 0 else "+"
                parts.append("%s %f%s" % (sym, abs(coef), x_str))
        return " ".join(parts)

    @classmethod
    def fit(cls, coords):
        xlist = [c[0] for c in coords]
        ylist = [c[1] for c in coords]
        count = len(coords)
        sum_x = sum(xlist)
        sum_y = sum(ylist)
        sum_x2 = sum([x**2 for x in xlist])
        sum_x3 = sum([x**3 for x in xlist])
        sum_x4 = sum([x**4 for x in xlist])
        sum_xy = sum([x * y for x, y in coords])
        sum_x2y = sum([y*x**2 for x, y in coords])
        vector_b = [sum_y, sum_xy, sum_x2y]
        m = [
            [count, sum_x, sum_x2],
            [sum_x, sum_x2, sum_x3],
            [sum_x2, sum_x3, sum_x4]
        ]
        m0 = [vector_b, m[1], m[2]]
        m1 = [m[0], vector_b, m[2]]
        m2 = [m[0], m[1], vector_b]
        det_m = calc_determinant(m)
        a0 = calc_determinant(m0) / det_m
        a1 = calc_determinant(m1) / det_m
        a2 = calc_determinant(m2) / det_m
        return cls(a0, a1, a2)


######################################################################
# Internal Temperature Sensor with Drift Compensation
######################################################################

class InternalTemperatureSensor:
    """Internal temperature sensor with smoothing and calibration tracking"""
    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name()
        smooth_time = config.getfloat("smooth_time", 2., above=0.)
        self.inv_smooth_time = 1. / smooth_time
        self.min_temp = config.getfloat(
            "min_temperature", KELVIN_TO_CELSIUS, minval=KELVIN_TO_CELSIUS
        )
        self.max_temp = config.getfloat(
            "max_temperature", 99999999.9, above=self.min_temp
        )
        # Setup physical sensor using standard Klipper sensor configuration
        # This uses the sensor_type, sensor_pin, etc. from config
        pheaters = self.printer.load_object(config, "heaters")
        self.sensor = pheaters.setup_sensor(config)
        self.sensor.setup_minmax(self.min_temp, self.max_temp)
        self.sensor.setup_callback(self._temp_callback)
        pheaters.register_sensor(config, self)
        
        # Temperature tracking
        self.last_temp_read_time = 0.
        self.last_measurement = (0., 99999999., 0.,)
        self._callbacks = []

    def _temp_callback(self, read_time, temp):
        smoothed_temp, measured_min, measured_max = self.last_measurement
        time_diff = read_time - self.last_temp_read_time
        self.last_temp_read_time = read_time
        temp_diff = temp - smoothed_temp
        adj_time = min(time_diff * self.inv_smooth_time, 1.)
        smoothed_temp += temp_diff * adj_time
        measured_min = min(measured_min, smoothed_temp)
        measured_max = max(measured_max, smoothed_temp)
        self.last_measurement = (smoothed_temp, measured_min, measured_max)
        # Notify any registered callbacks
        for callback in self._callbacks:
            callback(smoothed_temp)

    def register_callback(self, callback):
        """Register a callback to be called when temperature updates"""
        self._callbacks.append(callback)

    def get_temp(self, eventtime=None):
        """Return current smoothed temperature"""
        return self.last_measurement[0]

    def get_status(self, eventtime=None):
        smoothed_temp, measured_min, measured_max = self.last_measurement
        return {
            "temperature": smoothed_temp,
            "measured_min_temp": round(measured_min, 2),
            "measured_max_temp": round(measured_max, 2),
        }

    def stats(self, eventtime):
        return False, 'temp_sensor: temp=%.1f' % (self.last_measurement[0])


######################################################################
# Drift Compensation Engine
######################################################################

class DriftCompensationEngine:
    """Handles temperature-based frequency drift compensation"""
    def __init__(self, config, temp_sensor):
        self.printer = config.get_printer()
        self.temp_sensor = temp_sensor
        self.name = config.get_name()
        
        # Calibration temperature at time of z-offset calibration
        self.cal_temp = config.getfloat("calibration_temp", 0.)
        
        # Drift compensation polynomials
        self.drift_calibration = None
        self.calibration_samples = None
        self.max_valid_temp = config.getfloat("max_validation_temp", 60.)
        self.dc_min_temp = config.getfloat("drift_calibration_min_temp", 0.)
        self.min_freq = 999999999999.
        
        # Load existing drift calibration if available
        dc = config.getlists(
            "drift_calibration", None, seps=(',', '\n'), parser=float
        )
        if dc is not None:
            for coefs in dc:
                if len(coefs) != 3:
                    raise config.error(
                        "Invalid polynomial in drift calibration"
                    )
            self.drift_calibration = [Polynomial2d(*coefs) for coefs in dc]
            cal = self.drift_calibration
            start_temp, end_temp = self.dc_min_temp, self.max_valid_temp
            self._check_calibration(cal, start_temp, end_temp, config.error)
            low_poly = self.drift_calibration[-1]
            self.min_freq = min([low_poly(temp) for temp in range(121)])
            cal_str = "\n".join([repr(p) for p in cal])
            logging.info(
                "%s: loaded temperature drift calibration. Min Temp: %.2f,"
                " Min Freq: %.6f\n%s"
                % (self.name, self.dc_min_temp, self.min_freq, cal_str)
            )
        else:
            logging.info(
                "%s: No drift calibration configured, disabling temperature "
                "drift compensation"
                % (self.name,)
            )
        
        self.enabled = has_dc = self.drift_calibration is not None
        if self.cal_temp < 1e-6 and has_dc:
            self.enabled = False
            logging.info(
                "%s: No temperature saved for eddy probe calibration, "
                "disabling temperature drift compensation."
                % (self.name,)
            )

    def is_enabled(self):
        return self.enabled

    def set_enabled(self, enabled):
        if enabled:
            if self.drift_calibration is None:
                raise ValueError(
                    "No drift calibration configured, cannot enable "
                    "temperature drift compensation"
                )
            if self.cal_temp < 1e-6:
                raise ValueError(
                    "Z Calibration temperature not configured, cannot enable "
                    "temperature drift compensation"
                )
        self.enabled = enabled

    def note_z_calibration_start(self):
        self.cal_temp = self.temp_sensor.get_temp()

    def note_z_calibration_finish(self):
        self.cal_temp = (self.cal_temp + self.temp_sensor.get_temp()) / 2.0
        configfile = self.printer.lookup_object('configfile')
        configfile.set(self.name, "calibration_temp", "%.6f " % (self.cal_temp))
        gcode = self.printer.lookup_object("gcode")
        gcode.respond_info(
            "%s: Z Calibration Temperature set to %.2f. "
            "The SAVE_CONFIG command will update the printer config "
            "file and restart the printer."
            % (self.name, self.cal_temp)
        )

    def start_calibration(self):
        self.enabled = False
        self.calibration_samples = [[] for _ in range(DRIFT_SAMPLE_COUNT)]

    def collect_sample(self, probe_obj, kin_pos, tool_zero_z, speeds):
        """Collect calibration sample at current temperature"""
        if self.calibration_samples is None:
            self.calibration_samples = [[] for _ in range(DRIFT_SAMPLE_COUNT)]
        
        move_times = []
        temps = [0. for _ in range(DRIFT_SAMPLE_COUNT)]
        probe_samples = [[] for _ in range(DRIFT_SAMPLE_COUNT)]
        toolhead = self.printer.lookup_object("toolhead")
        cur_pos = toolhead.get_position()
        lift_speed, probe_speed, _ = speeds

        def _on_bulk_data_recd(msg):
            if move_times:
                idx, start_time, end_time = move_times[0]
                cur_temp = self.temp_sensor.get_temp()
                for sample in msg["data"]:
                    ptime = sample[0]
                    while ptime > end_time:
                        move_times.pop(0)
                        if not move_times:
                            return idx >= DRIFT_SAMPLE_COUNT - 1
                        idx, start_time, end_time = move_times[0]
                    if ptime < start_time:
                        continue
                    temps[idx] = cur_temp
                    probe_samples[idx].append(sample)
            return True
        
        probe_obj.add_client(_on_bulk_data_recd)
        
        for i in range(DRIFT_SAMPLE_COUNT):
            if i == 0:
                # Move down to first sample location
                cur_pos[2] = tool_zero_z + .05
            else:
                # Sample each .5mm in z
                cur_pos[2] += 1.
                toolhead.manual_move(cur_pos, lift_speed)
                cur_pos[2] -= .5
            toolhead.manual_move(cur_pos, probe_speed)
            start = toolhead.get_last_move_time() + .05
            end = start + .1
            move_times.append((i, start, end))
            toolhead.dwell(.2)
        
        toolhead.wait_moves()
        
        # Wait for sample collection to finish
        reactor = self.printer.get_reactor()
        evttime = reactor.monotonic()
        while move_times:
            evttime = reactor.pause(evttime + .1)
        
        sample_temp = sum(temps) / len(temps)
        for i, data in enumerate(probe_samples):
            freqs = [d[1] for d in data]
            zvals = [d[2] for d in data]
            avg_freq = sum(freqs) / len(freqs)
            avg_z = sum(zvals) / len(zvals)
            kin_z = i * .5 + .05 + kin_pos[2]
            logging.info(
                "Probe Values at Temp %.2fC, Z %.4fmm: Avg Freq = %.6f, "
                "Avg Measured Z = %.6f"
                % (sample_temp, kin_z, avg_freq, avg_z)
            )
            self.calibration_samples[i].append((sample_temp, avg_freq))
        
        return sample_temp

    def finish_calibration(self, success):
        cal_samples = self.calibration_samples
        self.calibration_samples = None
        if not success:
            return
        gcode = self.printer.lookup_object("gcode")
        if len(cal_samples) < 3:
            raise gcode.error(
                "calibration error, not enough samples"
            )
        min_temp, _ = cal_samples[0][0]
        max_temp, _ = cal_samples[-1][0]
        polynomials = []
        for i, coords in enumerate(cal_samples):
            height = .05 + i * .5
            poly = Polynomial2d.fit(coords)
            polynomials.append(poly)
            logging.info("Polynomial at Z=%.2f: %s" % (height, repr(poly)))
        end_vld_temp = max(self.max_valid_temp, max_temp)
        self._check_calibration(polynomials, min_temp, end_vld_temp)
        coef_cfg = "\n" + "\n".join([str(p) for p in polynomials])
        configfile = self.printer.lookup_object('configfile')
        configfile.set(self.name, "drift_calibration", coef_cfg)
        configfile.set(self.name, "drift_calibration_min_temp", min_temp)
        gcode.respond_info(
            "%s: generated %d 2D polynomials\n"
            "The SAVE_CONFIG command will update the printer config "
            "file and restart the printer."
            % (self.name, len(polynomials))
        )

    def _check_calibration(self, calibration, start_temp, end_temp, error=None):
        error = error or self.printer.command_error
        start = int(start_temp)
        end = int(end_temp) + 1
        for temp in range(start, end, 1):
            last_freq = calibration[0](temp)
            for i, poly in enumerate(calibration[1:]):
                next_freq = poly(temp)
                if next_freq >= last_freq:
                    # invalid polynomial
                    raise error(
                        "%s: invalid calibration detected, curve at index "
                        "%d overlaps previous curve at temp %dC."
                        % (self.name, i + 1, temp)
                    )
                last_freq = next_freq

    def adjust_freq(self, freq, origin_temp=None):
        """Adjust frequency from current temperature toward calibration temperature"""
        if not self.enabled or freq < self.min_freq:
            return freq
        if origin_temp is None:
            origin_temp = self.temp_sensor.get_temp()
        return self._calc_freq(freq, origin_temp, self.cal_temp)

    def unadjust_freq(self, freq, dest_temp=None):
        """Unadjust frequency to compensate for temperature change"""
        if not self.enabled or freq < self.min_freq:
            return freq
        if dest_temp is None:
            dest_temp = self.temp_sensor.get_temp()
        return self._calc_freq(freq, self.cal_temp, dest_temp)

    def _calc_freq(self, freq, origin_temp, dest_temp):
        high_freq = low_freq = None
        dc = self.drift_calibration
        for pos, poly in enumerate(dc):
            high_freq = low_freq
            low_freq = poly(origin_temp)
            if freq >= low_freq:
                if high_freq is None:
                    # Frequency above max calibration value
                    err = poly(dest_temp) - low_freq
                    return freq + err
                t = min(1., max(0., (freq - low_freq) / (high_freq - low_freq)))
                low_tgt_freq = poly(dest_temp)
                high_tgt_freq = dc[pos-1](dest_temp)
                return (1 - t) * low_tgt_freq + t * high_tgt_freq
        # Frequency below minimum, no correction
        return freq

    def get_temperature(self):
        return self.temp_sensor.get_temp()


######################################################################
# Eddy Current Calibration
######################################################################

class EddyCalibration:
    def __init__(self, config, drift_comp):
        self.printer = config.get_printer()
        self.name = config.get_name()
        self.drift_comp = drift_comp
        # Current calibration data
        self.cal_freqs = []
        self.cal_zpos = []
        cal = config.get('calibrate', None)
        if cal is not None:
            cal = [list(map(float, d.strip().split(':', 1)))
                   for d in cal.split(',')]
            self.load_calibration(cal)
        # Probe calibrate state
        self.probe_speed = 0.
        # Register commands
        cname = self.name.split()[-1]
        gcode = self.printer.lookup_object('gcode')
        gcode.register_mux_command("PROBE_EDDY_CURRENT_CALIBRATE", "CHIP",
                                   cname, self.cmd_EDDY_CALIBRATE,
                                   desc=self.cmd_EDDY_CALIBRATE_help)
        gcode.register_command('Z_OFFSET_APPLY_PROBE',
                               self.cmd_Z_OFFSET_APPLY_PROBE,
                               desc=self.cmd_Z_OFFSET_APPLY_PROBE_help)

    def is_calibrated(self):
        return len(self.cal_freqs) > 2

    def load_calibration(self, cal):
        cal = sorted([(c[1], c[0]) for c in cal])
        self.cal_freqs = [c[0] for c in cal]
        self.cal_zpos = [c[1] for c in cal]

    def apply_calibration(self, samples):
        cur_temp = self.drift_comp.get_temperature()
        for i, (samp_time, freq, dummy_z) in enumerate(samples):
            adj_freq = self.drift_comp.adjust_freq(freq, cur_temp)
            pos = bisect.bisect(self.cal_freqs, adj_freq)
            if pos >= len(self.cal_zpos):
                zpos = -OUT_OF_RANGE
            elif pos == 0:
                zpos = OUT_OF_RANGE
            else:
                # XXX - could further optimize and avoid div by zero
                this_freq = self.cal_freqs[pos]
                prev_freq = self.cal_freqs[pos - 1]
                this_zpos = self.cal_zpos[pos]
                prev_zpos = self.cal_zpos[pos - 1]
                gain = (this_zpos - prev_zpos) / (this_freq - prev_freq)
                offset = prev_zpos - prev_freq * gain
                zpos = adj_freq * gain + offset
            samples[i] = (samp_time, freq, round(zpos, 6))

    def freq_to_height(self, freq):
        dummy_sample = [(0., freq, 0.)]
        self.apply_calibration(dummy_sample)
        return dummy_sample[0][2]

    def height_to_freq(self, height):
        # XXX - could optimize lookup
        rev_zpos = list(reversed(self.cal_zpos))
        rev_freqs = list(reversed(self.cal_freqs))
        pos = bisect.bisect(rev_zpos, height)
        if pos == 0 or pos >= len(rev_zpos):
            raise self.printer.command_error(
                "Invalid probe_eddy_current height")
        this_freq = rev_freqs[pos]
        prev_freq = rev_freqs[pos - 1]
        this_zpos = rev_zpos[pos]
        prev_zpos = rev_zpos[pos - 1]
        gain = (this_freq - prev_freq) / (this_zpos - prev_zpos)
        offset = prev_freq - prev_zpos * gain
        freq = height * gain + offset
        return self.drift_comp.unadjust_freq(freq)

    def do_calibration_moves(self, move_speed):
        toolhead = self.printer.lookup_object('toolhead')
        kin = toolhead.get_kinematics()
        move = toolhead.manual_move
        # Start data collection
        msgs = []
        is_finished = False
        def handle_batch(msg):
            if is_finished:
                return False
            msgs.append(msg)
            return True
        self.printer.lookup_object(self.name).add_client(handle_batch)
        toolhead.dwell(1.)
        self.drift_comp.note_z_calibration_start()
        # Move to each 40um position
        max_z = 4.0
        samp_dist = 0.040
        req_zpos = [i*samp_dist for i in range(int(max_z / samp_dist) + 1)]
        start_pos = toolhead.get_position()
        times = []
        for zpos in req_zpos:
            # Move to next position (always descending to reduce backlash)
            hop_pos = list(start_pos)
            hop_pos[2] += zpos + 0.500
            move(hop_pos, move_speed)
            next_pos = list(start_pos)
            next_pos[2] += zpos
            move(next_pos, move_speed)
            # Note sample timing
            start_query_time = toolhead.get_last_move_time() + 0.050
            end_query_time = start_query_time + 0.100
            toolhead.dwell(0.200)
            # Find Z position based on actual commanded stepper position
            toolhead.flush_step_generation()
            kin_spos = {s.get_name(): s.get_commanded_position()
                        for s in kin.get_steppers()}
            kin_pos = kin.calc_position(kin_spos)
            times.append((start_query_time, end_query_time, kin_pos[2]))
        toolhead.dwell(1.0)
        toolhead.wait_moves()
        self.drift_comp.note_z_calibration_finish()
        # Finish data collection
        is_finished = True
        # Correlate query responses
        cal = {}
        step = 0
        for msg in msgs:
            for query_time, freq, old_z in msg['data']:
                # Add to step tracking
                while step < len(times) and query_time > times[step][1]:
                    step += 1
                if step < len(times) and query_time >= times[step][0]:
                    cal.setdefault(times[step][2], []).append(freq)
        if len(cal) != len(times):
            raise self.printer.command_error(
                "Failed calibration - incomplete sensor data")
        return cal

    def _median(self, values):
        values = sorted(values)
        n = len(values)
        if n % 2 == 0:
            return (values[n//2 - 1] + values[n//2]) / 2.0
        return values[n // 2]

    def calc_freqs(self, meas):
        positions = {}
        for pos, freqs in meas.items():
            count = len(freqs)
            freq_avg = float(sum(freqs)) / count
            mads = [abs(f - freq_avg) for f in freqs]
            mad = self._median(mads)
            positions[pos] = (freq_avg, mad, count)
        return positions

    def validate_calibration_data(self, positions):
        last_freq = 40000000.
        last_pos = last_mad = .0
        gcode = self.printer.lookup_object("gcode")
        filtered = []
        mad_hz_total = .0
        mad_mm_total = .0
        samples_count = 0
        for pos, (freq_avg, mad_hz, count) in sorted(positions.items()):
            if freq_avg > last_freq:
                gcode.respond_info(
                    "Frequency stops decreasing at step %.3f" % (pos))
                break
            diff_mad = math.sqrt(last_mad**2 + mad_hz**2)
            # Calculate if samples have a significant difference
            freq_diff = last_freq - freq_avg
            last_freq = freq_avg
            if freq_diff < 2.5 * diff_mad:
                gcode.respond_info(
                    "Frequency too noisy at step %.3f -> %.3f" % (
                        last_pos, pos))
                gcode.respond_info(
                    "Frequency diff: %.3f, MAD_Hz: %.3f -> MAD_Hz: %.3f" % (
                        freq_diff, last_mad, mad_hz
                    ))
                break
            last_mad = mad_hz
            delta_dist = pos - last_pos
            last_pos = pos
            # MAD is Median Absolute Deviation to Frequency avg ~ delta_hz_1
            # Signal is delta_hz_2 / delta_dist
            # SNR ~= delta_hz_1 / (delta_hz_2 / delta_mm) = d_1 * d_mm / d_2
            mad_mm = mad_hz * delta_dist / freq_diff
            filtered.append((pos, freq_avg, mad_hz, mad_mm))
            mad_hz_total += mad_hz
            mad_mm_total += mad_mm
            samples_count += count
        avg_mad = mad_hz_total / len(filtered)
        avg_mad_mm = mad_mm_total / len(filtered)
        gcode.respond_info(
            "probe_eddy_current: noise %.6fmm, MAD_Hz=%.3f in %d queries\n" % (
                avg_mad_mm, avg_mad, samples_count))
        freq_list = [freq for _, freq, _, _ in filtered]
        freq_diff = max(freq_list) - min(freq_list)
        gcode.respond_info("Total frequency range: %.3f Hz\n" % (freq_diff))
        points = [0.25, 0.5, 1.0, 2.0, 3.0]
        for pos, _, mad_hz, mad_mm in filtered:
            if len(points) and points[0] <= pos:
                points.pop(0)
                msg = "z_offset: %.3f # noise %.6fmm, MAD_Hz=%.3f\n" % (
                    pos, mad_mm, mad_hz)
                gcode.respond_info(msg)
        return filtered

    def post_manual_probe(self, kin_pos):
        if kin_pos is None:
            # Manual Probe was aborted
            return
        curpos = list(kin_pos)
        move = self.printer.lookup_object('toolhead').manual_move
        # Move away from the bed
        probe_calibrate_z = curpos[2]
        curpos[2] += 5.
        move(curpos, self.probe_speed)
        # Move sensor over nozzle position
        pprobe = self.printer.lookup_object("probe")
        x_offset, y_offset, z_offset = pprobe.get_offsets()
        curpos[0] -= x_offset
        curpos[1] -= y_offset
        move(curpos, self.probe_speed)
        # Descend back to bed
        curpos[2] -= 5. - 0.050
        move(curpos, self.probe_speed)
        # Perform calibration movement and capture
        cal = self.do_calibration_moves(self.probe_speed)
        # Calculate each sample position average and variance
        _positions = self.calc_freqs(cal)
        # Fix Z position offset
        positions = {}
        for k in _positions:
            v = _positions[k]
            k = k - probe_calibrate_z
            positions[k] = v
        filtered = self.validate_calibration_data(positions)
        if len(filtered) <= 8:
           raise self.printer.command_error(
              "Failed calibration - No usable data")
        z_freq_pairs = [(pos, freq) for pos, freq, _, _ in filtered]
        self._save_calibration(z_freq_pairs)

    def _save_calibration(self, z_freq_pairs):
        gcode = self.printer.lookup_object("gcode")
        gcode.respond_info(
            "The SAVE_CONFIG command will update the printer config file\n"
            "and restart the printer.")
        # Save results
        cal_contents = []
        for i, (pos, freq) in enumerate(z_freq_pairs):
            if not i % 3:
                cal_contents.append('\n')
            cal_contents.append("%.6f:%.3f" % (pos, freq))
            cal_contents.append(',')
        cal_contents.pop()
        configfile = self.printer.lookup_object('configfile')
        configfile.set(self.name, 'calibrate', ''.join(cal_contents))

    cmd_EDDY_CALIBRATE_help = "Calibrate eddy current probe"
    def cmd_EDDY_CALIBRATE(self, gcmd):
        self.probe_speed = gcmd.get_float("PROBE_SPEED", 5., above=0.)
        # Start manual probe
        manual_probe.ManualProbeHelper(self.printer, gcmd,
                                       self.post_manual_probe)

    cmd_Z_OFFSET_APPLY_PROBE_help = "Adjust the probe's z_offset"
    def cmd_Z_OFFSET_APPLY_PROBE(self, gcmd):
        gcode_move = self.printer.lookup_object("gcode_move")
        offset = gcode_move.get_status()['homing_origin'].z
        if offset == 0:
            gcmd.respond_info("Nothing to do: Z Offset is 0")
            return
        cal_zpos = [z - offset for z in self.cal_zpos]
        z_freq_pairs = zip(cal_zpos, self.cal_freqs)
        z_freq_pairs = sorted(z_freq_pairs)
        self._save_calibration(z_freq_pairs)


######################################################################
# Eddy Current Probe Sample Gathering
######################################################################

class EddyGatherSamples:
    def __init__(self, printer, sensor_helper, calibration, z_offset):
        self._printer = printer
        self._sensor_helper = sensor_helper
        self._calibration = calibration
        self._z_offset = z_offset
        # Results storage
        self._samples = []
        self._probe_times = []
        self._probe_results = []
        self._need_stop = False
        # Start samples
        if not self._calibration.is_calibrated():
            raise self._printer.command_error(
                "Must calibrate probe_eddy_current first")
        sensor_helper.add_client(self._add_measurement)

    def _add_measurement(self, msg):
        if self._need_stop:
            del self._samples[:]
            return False
        self._samples.append(msg)
        self._check_samples()
        return True

    def finish(self):
        self._need_stop = True

    def _await_samples(self):
        # Make sure enough samples have been collected
        reactor = self._printer.get_reactor()
        mcu = self._sensor_helper.get_mcu()
        while self._probe_times:
            start_time, end_time, pos_time, toolhead_pos = self._probe_times[0]
            systime = reactor.monotonic()
            est_print_time = mcu.estimated_print_time(systime)
            if est_print_time > end_time + 1.0:
                raise self._printer.command_error(
                    "probe_eddy_current sensor outage")
            reactor.pause(systime + 0.010)

    def _pull_freq(self, start_time, end_time):
        # Find average sensor frequency between time range
        msg_num = discard_msgs = 0
        samp_sum = 0.
        samp_count = 0
        while msg_num < len(self._samples):
            msg = self._samples[msg_num]
            msg_num += 1
            data = msg['data']
            if data[0][0] > end_time:
                break
            if data[-1][0] < start_time:
                discard_msgs = msg_num
                continue
            for time, freq, z in data:
                if time >= start_time and time <= end_time:
                    samp_sum += freq
                    samp_count += 1
        del self._samples[:discard_msgs]
        if not samp_count:
            # No sensor readings - raise error in pull_probed()
            return 0.
        return samp_sum / samp_count

    def _lookup_toolhead_pos(self, pos_time):
        toolhead = self._printer.lookup_object('toolhead')
        kin = toolhead.get_kinematics()
        kin_spos = {s.get_name(): s.mcu_to_commanded_position(
                                      s.get_past_mcu_position(pos_time))
                    for s in kin.get_steppers()}
        return kin.calc_position(kin_spos)

    def _check_samples(self):
        while self._samples and self._probe_times:
            start_time, end_time, pos_time, toolhead_pos = self._probe_times[0]
            if self._samples[-1]['data'][-1][0] < end_time:
                break
            freq = self._pull_freq(start_time, end_time)
            if pos_time is not None:
                toolhead_pos = self._lookup_toolhead_pos(pos_time)
            sensor_z = None
            if freq:
                sensor_z = self._calibration.freq_to_height(freq)
            self._probe_results.append((sensor_z, toolhead_pos))
            self._probe_times.pop(0)

    def pull_probed(self):
        self._await_samples()
        results = []
        for sensor_z, toolhead_pos in self._probe_results:
            if sensor_z is None:
                raise self._printer.command_error(
                    "Unable to obtain probe_eddy_current sensor readings")
            if sensor_z <= -OUT_OF_RANGE or sensor_z >= OUT_OF_RANGE:
                raise self._printer.command_error(
                    "probe_eddy_current sensor not in valid range")
            # Callers expect position relative to z_offset, so recalculate
            bed_deviation = toolhead_pos[2] - sensor_z
            toolhead_pos[2] = self._z_offset + bed_deviation
            results.append(toolhead_pos)
        del self._probe_results[:]
        return results

    def note_probe(self, start_time, end_time, toolhead_pos):
        self._probe_times.append((start_time, end_time, None, toolhead_pos))
        self._check_samples()

    def note_probe_and_position(self, start_time, end_time, pos_time):
        self._probe_times.append((start_time, end_time, pos_time, None))
        self._check_samples()


######################################################################
# Eddy Current Probe Descent Engine
######################################################################

class EddyDescend:
    REASON_SENSOR_ERROR = mcu.MCU_trsync.REASON_COMMS_TIMEOUT + 1
    def __init__(self, config, sensor_helper, calibration, param_helper):
        self._printer = config.get_printer()
        self._sensor_helper = sensor_helper
        self._mcu = sensor_helper.get_mcu()
        self._calibration = calibration
        self._param_helper = param_helper
        self._z_min_position = probe.lookup_minimum_z(config)
        self._z_offset = config.getfloat('z_offset', minval=0.)
        self._dispatch = mcu.TriggerDispatch(self._mcu)
        self._trigger_time = 0.
        self._gather = None
        probe.LookupZSteppers(config, self._dispatch.add_stepper)

    # Interface for phoming.probing_move()
    def get_steppers(self):
        return self._dispatch.get_steppers()

    def home_start(self, print_time, sample_time, sample_count, rest_time,
                   triggered=True):
        self._trigger_time = 0.
        trigger_freq = self._calibration.height_to_freq(self._z_offset)
        trigger_completion = self._dispatch.start(print_time)
        self._sensor_helper.setup_home(
            print_time, trigger_freq, self._dispatch.get_oid(),
            mcu.MCU_trsync.REASON_ENDSTOP_HIT, self.REASON_SENSOR_ERROR)
        return trigger_completion

    def home_wait(self, home_end_time):
        self._dispatch.wait_end(home_end_time)
        trigger_time = self._sensor_helper.clear_home()
        res = self._dispatch.stop()
        if res >= mcu.MCU_trsync.REASON_COMMS_TIMEOUT:
            if res == mcu.MCU_trsync.REASON_COMMS_TIMEOUT:
                raise self._printer.command_error(
                    "Communication timeout during homing")
            error_code = res - self.REASON_SENSOR_ERROR
            error_msg = self._sensor_helper.lookup_sensor_error(error_code)
            raise self._printer.command_error(error_msg)
        if res != mcu.MCU_trsync.REASON_ENDSTOP_HIT:
            return 0.
        if self._mcu.is_fileoutput():
            return home_end_time
        self._trigger_time = trigger_time
        return trigger_time

    # Probe session interface
    def start_probe_session(self, gcmd):
        self._gather = EddyGatherSamples(self._printer, self._sensor_helper,
                                         self._calibration, self._z_offset)
        return self

    def run_probe(self, gcmd):
        toolhead = self._printer.lookup_object('toolhead')
        pos = toolhead.get_position()
        pos[2] = self._z_min_position
        speed = self._param_helper.get_probe_params(gcmd)['probe_speed']
        # Perform probing move
        phoming = self._printer.lookup_object('homing')
        trig_pos = phoming.probing_move(self, pos, speed)
        if not self._trigger_time:
            return trig_pos
        # Extract samples
        start_time = self._trigger_time + 0.050
        end_time = start_time + 0.100
        toolhead_pos = toolhead.get_position()
        self._gather.note_probe(start_time, end_time, toolhead_pos)

    def pull_probed_results(self):
        return self._gather.pull_probed()

    def end_probe_session(self):
        self._gather.finish()
        self._gather = None


######################################################################
# Eddy Endstop Wrapper
######################################################################

class EddyEndstopWrapper:
    def __init__(self, sensor_helper, eddy_descend):
        self._sensor_helper = sensor_helper
        self._eddy_descend = eddy_descend
        self._hw_probe_session = None

    # Interface for MCU_endstop
    def get_mcu(self):
        return self._sensor_helper.get_mcu()

    def add_stepper(self, stepper):
        pass

    def get_steppers(self):
        return self._eddy_descend.get_steppers()

    def home_start(self, print_time, sample_time, sample_count, rest_time,
                   triggered=True):
        return self._eddy_descend.home_start(
            print_time, sample_time, sample_count, rest_time, triggered)

    def home_wait(self, home_end_time):
        return self._eddy_descend.home_wait(home_end_time)

    def query_endstop(self, print_time):
        return False # XXX

    # Interface for HomingViaProbeHelper
    def multi_probe_begin(self):
        self._hw_probe_session = self._eddy_descend.start_probe_session(None)

    def multi_probe_end(self):
        self._hw_probe_session.end_probe_session()
        self._hw_probe_session = None

    def probe_prepare(self, hmove):
        pass

    def probe_finish(self, hmove):
        pass

    def get_position_endstop(self):
        return self._eddy_descend._z_offset


######################################################################
# Eddy Current Scanning Probe
######################################################################

class EddyScanningProbe:
    def __init__(self, printer, sensor_helper, calibration, z_offset, gcmd):
        self._printer = printer
        self._sensor_helper = sensor_helper
        self._calibration = calibration
        self._z_offset = z_offset
        self._gather = EddyGatherSamples(printer, sensor_helper,
                                         calibration, z_offset)
        self._sample_time_delay = 0.050
        self._sample_time = gcmd.get_float("SAMPLE_TIME", 0.100, above=0.0)
        self._is_rapid = gcmd.get("METHOD", "scan") == 'rapid_scan'

    def _rapid_lookahead_cb(self, printtime):
        start_time = printtime - self._sample_time / 2
        self._gather.note_probe_and_position(
            start_time, start_time + self._sample_time, printtime)

    def run_probe(self, gcmd):
        toolhead = self._printer.lookup_object("toolhead")
        if self._is_rapid:
            toolhead.register_lookahead_callback(self._rapid_lookahead_cb)
            return
        printtime = toolhead.get_last_move_time()
        toolhead.dwell(self._sample_time_delay + self._sample_time)
        start_time = printtime + self._sample_time_delay
        self._gather.note_probe_and_position(
            start_time, start_time + self._sample_time, start_time)

    def pull_probed_results(self):
        if self._is_rapid:
            # Flush lookahead (so all lookahead callbacks are invoked)
            toolhead = self._printer.lookup_object("toolhead")
            toolhead.get_last_move_time()
        results = self._gather.pull_probed()
        # Allow axis_twist_compensation to update results
        for epos in results:
            self._printer.send_event("probe:update_results", epos)
        return results

    def end_probe_session(self):
        self._gather.finish()
        self._gather = None


######################################################################
# Main Printer Object - Standalone Eddy Current Probe with Drift Compensation
######################################################################

class PrinterEddyProbeNoDrift:
    def __init__(self, config):
        self.printer = config.get_printer()
        
        # Setup internal temperature sensor with drift compensation
        # Temperature sensor uses: sensor_type, sensor_pin, min_temperature, 
        # max_temperature, smooth_time, horizontal_move_z
        self.temp_sensor = InternalTemperatureSensor(config)
        
        # Setup drift compensation engine
        self.drift_comp = DriftCompensationEngine(config, self.temp_sensor)
        
        # Setup eddy current calibration
        self.calibration = EddyCalibration(config, self.drift_comp)
        
        # Setup eddy current sensor (separate from temperature sensor)
        # Eddy sensor uses: eddy_sensor_type, i2c_address, i2c_bus, etc.
        eddy_sensors = { "ldc1612": ldc1612.LDC1612 }
        eddy_sensor_type = config.getchoice('eddy_sensor_type', {s: s for s in eddy_sensors})
        self.sensor_helper = eddy_sensors[eddy_sensor_type](config, self.calibration)
        
        # Probe interface
        self.param_helper = probe.ProbeParameterHelper(config)
        self.eddy_descend = EddyDescend(
            config, self.sensor_helper, self.calibration, self.param_helper)
        self.cmd_helper = probe.ProbeCommandHelper(config, self,
            replace_z_offset=True)
        self.probe_offsets = probe.ProbeOffsetsHelper(config)
        self.probe_session = probe.ProbeSessionHelper(
            config, self.param_helper, self.eddy_descend.start_probe_session)
        
        mcu_probe = EddyEndstopWrapper(self.sensor_helper, self.eddy_descend)
        probe.HomingViaProbeHelper(config, mcu_probe, self.param_helper)
        
        self.printer.add_object('probe', self)

    def add_client(self, cb):
        self.sensor_helper.add_client(cb)

    def get_probe_params(self, gcmd=None):
        return self.param_helper.get_probe_params(gcmd)

    def get_offsets(self):
        return self.probe_offsets.get_offsets()

    def get_status(self, eventtime):
        status = self.cmd_helper.get_status(eventtime)
        # Add temperature and drift compensation info
        temp_status = self.temp_sensor.get_status(eventtime)
        status.update({
            "temperature": temp_status["temperature"],
            "measured_min_temp": temp_status["measured_min_temp"],
            "measured_max_temp": temp_status["measured_max_temp"],
            "compensation_enabled": self.drift_comp.is_enabled(),
        })
        return status

    def start_probe_session(self, gcmd):
        method = gcmd.get('METHOD', 'automatic').lower()
        if method in ('scan', 'rapid_scan'):
            z_offset = self.get_offsets()[2]
            return EddyScanningProbe(self.printer, self.sensor_helper,
                                     self.calibration, z_offset, gcmd)
        return self.probe_session.start_probe_session(gcmd)


def load_config_prefix(config):
    return PrinterEddyProbeNoDrift(config)
