# Temperature Probe Module Documentation

## Overview

The `temperature_probe.py` module provides temperature sensing and drift compensation functionality for Kalico's eddy current probes. It's a port of the Klipper `temperature_probe.py` implementation, specifically designed to work with the BTT Eddy or BTT Eddy Coil probes used in Kalico-based machines.

### Purpose

Temperature changes affect the resonant frequency of eddy current probes, causing measurement errors. This module:

1. **Monitors temperature** - Continuously reads a temperature sensor
2. **Smooths readings** - Applies exponential smoothing to reduce noise
3. **Calibrates drift** - Creates polynomial models of how temperature affects probe frequency
4. **Compensates automatically** - Adjusts probe measurements based on temperature changes

## Configuration

### Section Name

```ini
[temperature_probe btt_eddy]
```

The section name matches the name of your `[probe_eddy_current]` section for automatic linking.

### Configuration Parameters

| Parameter | Default | Type | Description |
|-----------|---------|------|-------------|
| `sensor_type` | Required | string | Temperature sensor type (e.g., Generic 3950, MAX31865, AD595) |
| `sensor_pin` | Required | string | MCU pin for temperature sensor (e.g., eddy:gpio26) |
| `smooth_time` | 2.0 | float | Temperature smoothing time constant (seconds) |
| `min_temp` | -273.15 | float | Minimum allowed temperature (°C) |
| `max_temp` | 999999.9 | float | Maximum allowed temperature (°C) |
| `speed` | None | float | Manual move speed (uses probe speed if not set) |
| `horizontal_move_z` | 2.0 | float | Z height for horizontal movements (mm) |
| `resting_z` | 0.4 | float | Z height when at rest during calibration (mm) |
| `calibration_position` | None | list | XYZ position for calibration (e.g., 150, 150, 20) |
| `calibration_bed_temp` | None | float | Target bed temperature during calibration (°C) |
| `calibration_extruder_temp` | None | float | Target extruder temperature during calibration (°C) |
| `extruder_heating_z` | 50.0 | float | Z height while heating extruder (mm) |
| `calibration_temp` | 0.0 | float | Temperature at which Z offset was calibrated (auto-set) |
| `drift_calibration` | None | list | Polynomial coefficients for drift compensation (auto-generated) |
| `drift_calibration_min_temp` | 0.0 | float | Minimum temperature for drift compensation (auto-set) |
| `max_validation_temp` | 60.0 | float | Maximum temperature for validation (°C) |

### Example Configuration

#### Minimal Setup (No Drift Compensation)

```ini
[temperature_probe btt_eddy]
sensor_type: Generic 3950
sensor_pin: eddy:gpio26
```

#### Full Setup (With Drift Calibration)

```ini
[thermistor Generic 3950]
temperature1: 25.0
resistance1: 100000.0
temperature2: 150.0
resistance2: 1641.0
temperature3: 250.0
resistance3: 226.0

[temperature_probe btt_eddy]
sensor_type: Generic 3950
sensor_pin: eddy:gpio26
smooth_time: 2.0
min_temp: 0.0
max_temp: 300.0
calibration_position: 150, 150, 20
calibration_bed_temp: 65
calibration_extruder_temp: 240
```

## How It Works

### Temperature Smoothing

The temperature reading is smoothed using exponential smoothing to reduce noise from the sensor:

$$T_{smooth}(t) = T_{smooth}(t-1) + (T_{raw}(t) - T_{smooth}(t-1)) \cdot \min(1.0, \frac{\Delta t}{\text{smooth\_time}})$$

Where:
- `smooth_time` controls the responsiveness (higher = more smoothing)
- Default 2.0 seconds provides good balance

### Drift Compensation Model

Temperature drift is modeled as a set of 2D polynomials, one for each Z height:

$$f(z, T) = a_z + b_z \cdot T + c_z \cdot T^2$$

Where:
- `f(z, T)` is the probe frequency at height `z` and temperature `T`
- Coefficients `a`, `b`, `c` are fitted during calibration
- The probe has 9 calibration samples (0.05mm, 0.55mm, 1.05mm, ... 4.55mm)

### Calibration Process

1. **Initial Probe** - Manually probe to find Z=0 at starting temperature
2. **Heat & Sample** - As temperature increases, automatically collect samples at each step
3. **Manual Probing** - At each temperature step, manually probe to find current Z=0
4. **Fit Polynomials** - Generate temperature-frequency relationships for each height
5. **Save Calibration** - Store polynomials in config file

## G-Code Commands

### TEMPERATURE_PROBE_CALIBRATE

Start drift compensation calibration.

**Usage:**
```gcode
TEMPERATURE_PROBE_CALIBRATE PROBE=btt_eddy TARGET=60 STEP=2
```

**Parameters:**
- `PROBE` - Name of the temperature probe (required)
- `TARGET` - Target temperature in °C (required, must be above current)
- `STEP` - Temperature increment between samples in °C (optional, default 2.0, minimum 1.0)

**Process:**
1. Requires printer to be homed
2. Moves to calibration position if configured
3. Heats extruder and bed to starting temperatures
4. Prompts for first manual probe at initial temperature
5. Automatically advances and prompts for samples every STEP degrees
6. Requires minimum 3 samples for valid calibration

**Example:**
```gcode
G28                                         ; Home all axes
TEMPERATURE_PROBE_CALIBRATE PROBE=btt_eddy TARGET=60 STEP=5
; Follow on-screen prompts to position nozzle
TEMPERATURE_PROBE_NEXT                      ; (repeated automatically at temperature)
TEMPERATURE_PROBE_COMPLETE                  ; When done
```

### TEMPERATURE_PROBE_NEXT

Collect next calibration sample at a higher temperature.

**Usage:**
```gcode
TEMPERATURE_PROBE_NEXT
```

**Note:** This command is normally automatic - it runs when the target temperature is reached. Manual use is for testing or manual control.

### TEMPERATURE_PROBE_COMPLETE

Finish calibration successfully.

**Usage:**
```gcode
TEMPERATURE_PROBE_COMPLETE
```

**Result:** 
- Generates polynomials from collected samples
- Saves calibration to config file
- Requires SAVE_CONFIG to persist changes

### TEMPERATURE_PROBE_ENABLE

Enable or disable drift compensation.

**Usage:**
```gcode
TEMPERATURE_PROBE_ENABLE PROBE=btt_eddy ENABLE=1   ; Enable
TEMPERATURE_PROBE_ENABLE PROBE=btt_eddy ENABLE=0   ; Disable
```

## Status Information

Query temperature probe status:

```gcode
QUERY_PROBE PROBE=btt_eddy
```

Returns:
```
temperature: 24.5              # Current smoothed temperature (°C)
measured_min_temp: 24.2        # Minimum temperature seen
measured_max_temp: 25.1        # Maximum temperature seen
in_calibration: False          # Currently calibrating?
estimated_expansion: 0.05      # Total thermal expansion (mm)
compensation_enabled: True     # Is drift compensation active?
```

## Features

### Polynomial-Based Drift Correction

Instead of simple linear models, the module uses 2D polynomials to accurately model how probe frequency changes with temperature at different heights. This provides better accuracy across the full Z range.

### Automatic Temperature-Triggered Sampling

During calibration, the system automatically advances to the next sample location when the target temperature is reached, eliminating manual temperature management.

### Thermal Expansion Tracking

The module estimates total thermal expansion during calibration by comparing successive Z measurements, helping diagnose mechanical issues.

### Configuration Auto-Save

Calibration results are automatically written to the config file via the configfile object. Use `SAVE_CONFIG` to persist changes.

## Linking with Eddy Probe

The temperature probe automatically registers drift compensation with the `probe_eddy_current` section if both sections have matching names:

```ini
[probe_eddy_current btt_eddy]          # Name: "btt_eddy"
...

[temperature_probe btt_eddy]           # Name: "btt_eddy" - LINKS automatically
sensor_type: Generic 3950
sensor_pin: eddy:gpio26
```

### What Happens on Startup

1. `TemperatureProbe` initializes and sets up temperature sensor
2. Searches for `[probe_eddy_current btt_eddy]` section
3. If found, creates `EddyDriftCompensation` object
4. Registers drift compensation handler with the probe
5. Logs success or warning if probe not found

### Probe Integration

The drift compensation object provides methods to the probe:

- `adjust_freq()` - Adjust measured frequency to calibration temperature
- `unadjust_freq()` - Adjust measured frequency from calibration temperature
- `note_z_calibration_start()` - Record temperature at Z calibration start
- `note_z_calibration_finish()` - Save temperature at Z calibration end

## Troubleshooting

### Temperature Reading Shows Incorrect Value

**Problem:** Temperature is stuck at 0°C or shows NaN

**Solutions:**
1. Verify physical connection of temperature sensor
2. Check `sensor_pin` is correct for your MCU
3. Verify thermistor type matches actual hardware
4. For MAX31865 sensors, ensure SPI bus is configured correctly

### Module Doesn't Link with Probe

**Problem:** Log shows "No probe named btt_eddy configured"

**Solutions:**
1. Verify `[probe_eddy_current]` section exists
2. Check section name exactly matches between probe and temperature_probe
3. Ensure probe is loaded before temperature_probe

### Calibration Won't Start

**Problem:** "Printer must be homed before calibration"

**Solutions:**
1. Run `G28` to home all axes
2. Try again with `TEMPERATURE_PROBE_CALIBRATE`

### Not Enough Samples

**Problem:** "too few expected samples" error

**Solutions:**
1. Increase `TARGET` temperature
2. Decrease `STEP` temperature increment
3. Example: `TARGET=60 STEP=1.0` gives ~60 samples (good)
4. Minimum 3 samples required, but recommend 5+

### Polynomials Won't Fit

**Problem:** "invalid calibration detected, curve overlaps"

**Solutions:**
1. Ensure temperature sensor is stable during each sample
2. Increase `smooth_time` to reduce noise
3. Collect samples more slowly (smaller STEP value)
4. Check for mechanical/electrical issues affecting measurements

## Integration with Kalico

This module is designed to work specifically with Kalico's `probe_eddy_current.py` and Kalico's adapted `probe.py`. Key integration points:

1. **Sensor Registration** - Uses Klipper's heaters module to register temperature sensor
2. **G-Code Commands** - Registers mux commands with probe name
3. **Configuration** - Reads from config and writes calibration data
4. **Thermal Compensation** - Works with probe's frequency adjustment hooks

## Performance Considerations

### Smoothing Time Selection

- **smooth_time: 1.0** - Quick response, more noise, faster drift detection
- **smooth_time: 2.0** - Balanced response (recommended)
- **smooth_time: 5.0** - Slow response, less noise, delayed compensation

Choose based on your sensor noise level and how quickly temperature changes.

### Calibration Range

Calibration should cover:
- Minimum temperature: Room temperature (20-25°C)
- Maximum temperature: Operating temperature (50-70°C for bed, 200-240°C for nozzle)

Drift compensation is most accurate within the calibration range.

### Sampling Rate

Temperature is sampled whenever the sensor reports new data (typically 1-5 times per second). The smoothing filter ensures this doesn't introduce aliasing.

## Technical Details

### Class Structure

#### TemperatureProbe
Main class that:
- Initializes temperature sensor via heaters module
- Manages calibration state machine
- Implements G-Code command handlers
- Provides status information

#### EddyDriftCompensation
Helper class that:
- Manages polynomial coefficients
- Collects calibration samples
- Fits polynomials to data
- Applies frequency adjustments

#### Polynomial2d
Utility class for:
- Evaluating 2D polynomials
- Fitting polynomials to coordinate pairs
- String representation

### Constants

```python
KELVIN_TO_CELSIUS = -273.15          # Absolute zero in Celsius
DRIFT_SAMPLE_COUNT = 9               # Number of Z heights sampled during calibration
```

## See Also

- [Klipper Probe Calibrate Documentation](https://www.klipper3d.org/Probe_Calibrate.html)
- [probe_eddy_current.py Documentation](./probe_eddy_current_documentation.md)
- [Kalico Documentation](https://kalico.xyz/)
