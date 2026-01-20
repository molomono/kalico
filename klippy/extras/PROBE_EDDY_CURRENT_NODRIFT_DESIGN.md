# Standalone Eddy Current Probe with Internal Drift Compensation

## Overview

`probe_eddy_current_nodrift.py` is a merged and refactored version of `probe_eddy_current.py` and `temperature_probe.py` that provides a fully standalone eddy current probe with integrated temperature-based drift compensation.

## Key Design Goals

1. **Self-contained operation**: All drift compensation logic is handled internally without requiring modifications to the main `probe.py` file
2. **No external dependencies**: The probe object manages its own calibration, temperature sensing, and drift calculations
3. **Seamless integration**: Works as a drop-in replacement for the standard eddy current probe in Klipper configurations

## Architecture

### Component Structure

#### 1. **Polynomial2d & Helper Functions**
- Implements 2D polynomial fitting for drift calibration curves
- Used to model frequency drift as a function of temperature at different Z heights

#### 2. **InternalTemperatureSensor**
- Integrated temperature sensor handling
- Provides smoothed temperature readings with configurable smoothing time
- Maintains temperature min/max tracking for calibration
- Integrates with Klipper's heater system

#### 3. **DriftCompensationEngine**
- Core drift compensation logic
- Manages calibration data and polynomial models
- Handles frequency adjustment based on temperature changes
- Key methods:
  - `adjust_freq()`: Adjusts measured frequency for current temperature
  - `unadjust_freq()`: Reverse adjustment for frequency-to-height conversion
  - `collect_sample()`: Gathers calibration samples at different temperatures

#### 4. **EddyCalibration**
- Z-offset calibration using eddy current measurements
- Maintains frequency-to-height mapping
- Registers eddy calibration GCode commands
- Integrates with drift compensation during calibration moves

#### 5. **Probe Session Components**
- `EddyGatherSamples`: Collects sensor samples during probing
- `EddyDescend`: Implements probe descent and triggering
- `EddyEndstopWrapper`: Emulates MCU endstop interface
- `EddyScanningProbe`: Handles scanning probe operations

#### 6. **PrinterEddyProbeNoDrift** (Main Object)
- Orchestrates all components
- Provides probe interface compatible with Klipper
- Manages GCode command registration
- Handles status reporting

## Configuration

The probe is configured as a `probe_eddy_current_nodrift` section in `printer.cfg`:

```ini
[probe_eddy_current_nodrift probe_name]
sensor_type: ldc1612
i2c_address: 0x2a
i2c_bus: i2c0a
z_offset: 0.0

# Temperature sensor configuration
min_temp: -273.15
max_temp: 350.0
smooth_time: 2.0

# Calibration settings
calibrate: 0.0:100000.0, 1.0:95000.0, ...

# Drift compensation calibration (auto-generated during calibration)
calibration_temp: 20.5
drift_calibration: 
    1.234567, 0.123456, 0.001234,
    1.234567, 0.123456, 0.001234
drift_calibration_min_temp: 20.0
```

## Workflow

### Initial Setup

1. **Eddy Current Calibration** (`PROBE_EDDY_CURRENT_CALIBRATE`)
   - Performs Z-axis calibration moves
   - Records frequency measurements at known Z positions
   - Creates frequency-to-height mapping
   - Records calibration temperature

### Drift Compensation Calibration

The probe performs temperature-based calibration to build drift models:

1. Starts at room temperature
2. Heats to target temperature in steps
3. At each temperature step:
   - Manually probes to establish Z position
   - Collects frequency samples at multiple Z heights
   - Records temperature and frequency pairs
4. Generates 2D polynomials (one per Z height)
5. Stores calibration in config for future use

### Operation

During probing:
1. Current temperature is read from internal sensor
2. Measured frequency is adjusted based on:
   - Temperature difference from calibration
   - Polynomial models for current Z position
3. Adjusted frequency is converted to Z height
4. Height measurements are accurate regardless of temperature

## Key Features

### Internal Temperature Management
- Smoothed temperature readings
- Automatic temperature tracking
- Min/max temperature recording
- No external temperature sensor required

### Automatic Drift Compensation
- Transparent frequency adjustment
- Real-time temperature-based corrections
- Multiple calibration models (one per Z height)
- Graceful degradation if calibration incomplete

### Standalone Operation
- No modifications needed to `probe.py`
- Complete drift compensation in single module
- Full GCode command support
- Compatible with all Klipper probe interfaces

### Calibration Features
- Multi-point temperature calibration
- Polynomial fitting for smooth compensation
- Validation of calibration data
- Signal-to-noise ratio analysis

## GCode Commands

All standard eddy current probe commands are supported:

- `PROBE_EDDY_CURRENT_CALIBRATE`: Initial Z-offset calibration
- `Z_OFFSET_APPLY_PROBE`: Apply probe Z-offset changes
- `PROBE`: Standard probe command (with drift compensation)
- Temperature-specific commands for drift calibration

## Status Information

The probe provides real-time status:

```python
{
    "name": "probe_eddy_current_nodrift probe_name",
    "type": "eddy",
    "sample_retract_dist": 2.0,
    "samples": 1,
    "samples_result": "average",
    "z_offset": 0.0,
    "temperature": 23.45,           # Current smoothed temperature
    "measured_min_temp": 20.0,      # Min temp since last reset
    "measured_max_temp": 25.0,      # Max temp since last reset
    "compensation_enabled": true    # Drift compensation active
}
```

## Advantages Over Separate Components

### Original Approach (Two Files)
- `temperature_probe.py`: Handles temperature + drift calibration
- `probe_eddy_current.py`: Handles probe measurements
- Required: Manual integration between probe and temperature modules
- Limitation: Changes to `probe.py` needed for registration

### New Approach (Single File)
- ✓ All functionality in one self-contained module
- ✓ No modifications to existing Klipper files required
- ✓ Complete control over drift compensation
- ✓ Easier to maintain and debug
- ✓ Can be used as a drop-in alternative to standard eddy probe

## Technical Details

### Polynomial Fitting
- 2D quadratic polynomials: `f(T) = a + b*T + c*T²`
- Fitted to temperature vs. frequency measurements at each Z height
- Ensures smooth, continuous drift models across temperature range

### Frequency Adjustment Algorithm
- Maps measured frequency to calibration space
- Interpolates between polynomial models
- Handles out-of-range frequencies gracefully
- Bidirectional (adjust/unadjust) for flexibility

### Sample Collection
- 9 samples at 0.5mm intervals for each temperature step
- Robust averaging and outlier detection
- SNR calculation for quality assessment
- Automatic validation and filtering

## Future Extensions

Possible enhancements:
- Adaptive calibration refinement during operation
- Machine learning models for drift prediction
- Per-bed-area drift compensation
- Integration with other probe types
- Advanced filtering algorithms

## Compatibility

- **Klipper Version**: Compatible with Klipper 0.11+
- **MCU Support**: Any MCU supported by Klipper's homing system
- **Sensor Support**: LDC1612 (extensible to other eddy sensors)
- **Probe Interface**: Full compatibility with Klipper probe system

## Configuration Examples

### Minimal Configuration
```ini
[probe_eddy_current_nodrift my_probe]
sensor_type: ldc1612
i2c_address: 0x2a
z_offset: 2.5
```

### Full Configuration with Drift Compensation
```ini
[probe_eddy_current_nodrift my_probe]
sensor_type: ldc1612
i2c_address: 0x2a
i2c_bus: i2c0a
z_offset: 2.5
speed: 10.0
horizontal_move_z: 2.0

# Temperature sensor setup
min_temp: 0
max_temp: 100
smooth_time: 2.0

# Calibration data (auto-generated)
calibrate: 0.0:100000.0, 1.0:95000.0, 2.0:90000.0
calibration_temp: 20.5

# Drift compensation (auto-generated)
drift_calibration:
    1.234567, 0.123456, 0.001234,
    1.234567, 0.123456, 0.001234
```

## Usage Notes

1. **First Time Setup**:
   - Run `PROBE_EDDY_CURRENT_CALIBRATE` to establish Z-mapping
   - Then proceed with drift compensation calibration

2. **Drift Compensation Calibration**:
   - Use `TEMPERATURE_PROBE_CALIBRATE TARGET=80` to calibrate drift
   - System will automatically collect samples at temperature intervals
   - Follow manual probing prompts

3. **Enable/Disable Drift Compensation**:
   - Compensation is auto-enabled if calibration data exists
   - Can be toggled via `TEMPERATURE_PROBE_ENABLE ENABLE=0/1`

4. **Validation**:
   - System validates all calibration data during load
   - Invalid data is logged with diagnostic information
   - Gracefully disables compensation if data is invalid

## Troubleshooting

### Compensation Not Working
1. Check if `calibration_temp` is set and non-zero
2. Verify `drift_calibration` polynomials are present in config
3. Check logs for validation errors
4. Run calibration again if needed

### Noisy Measurements
1. Ensure temperature sensor is reading smoothly
2. Check `smooth_time` setting (increase if noisy)
3. Verify sensor PCB is clean and well-seated
4. Check for electromagnetic interference

### Calibration Failures
1. Ensure bed can reach target temperature
2. Allow adequate settling time between samples
3. Verify manual probe can find consistent positions
4. Check for z-axis binding or mechanical issues

---

## Author Notes

This merged implementation combines the strengths of both original modules:
- Temperature sensing and calibration from `temperature_probe.py`
- Eddy current probe mechanics from `probe_eddy_current.py`

The result is a more cohesive, maintainable system that requires no modifications to Klipper's core `probe.py` module while providing complete internal drift compensation capability.
