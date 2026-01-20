# Probe Eddy Current with Drift Compensation - User Guide

## Quick Start

### Option 1: Simple Eddy Probe (No Temperature Compensation)

Add this to your `printer.cfg`:

```ini
[probe_eddy_current_nodrift eddy_probe]
eddy_sensor_type: ldc1612
i2c_address: 0x2a
i2c_bus: i2c0a
x_offset: 0.0
y_offset: 25.0
z_offset: 2.0
```

### Option 2: Eddy Probe with Temperature-Based Drift Compensation

Add this to your `printer.cfg`:

```ini
# First define the thermistor type (if not already defined)
[thermistor Generic 3950]
temperature1: 25.0
resistance1: 100000.0
temperature2: 150.0
resistance2: 1641.0
temperature3: 250.0
resistance3: 226.0

# Add the temperature probe (same name as eddy probe below)
[temperature_probe eddy_probe]
sensor_type: Generic 3950
sensor_pin: PF5
min_temperature: 0.0
max_temperature: 300.0
smooth_time: 2.0

# Add the eddy probe (same name as temperature probe above)
[probe_eddy_current_nodrift eddy_probe]
eddy_sensor_type: ldc1612
i2c_address: 0x2a
i2c_bus: i2c0a
x_offset: 0.0
y_offset: 25.0
z_offset: 2.0
```

**Key Point:** Both sections must have the **same name** (`eddy_probe` in the example above) to be linked together.

## Architecture

The refactored module consists of two separate components:

### 1. Temperature Probe (`[temperature_probe NAME]`)

**Purpose:** Reads temperature sensor and provides smoothed temperature data

**Key Features:**
- Uses standard Klipper temperature sensor support
- Applies smoothing to reduce noise
- Tracks min/max temperatures
- Integrates with Klipper's heater system

**Configuration:**
```ini
[temperature_probe my_probe]
sensor_type: Generic 3950
sensor_pin: PF5
min_temperature: 0.0
max_temperature: 300.0
smooth_time: 2.0
```

**Status Information:**
```
{
  "temperature": 25.3,
  "measured_min_temp": 24.8,
  "measured_max_temp": 26.1
}
```

### 2. Eddy Current Probe (`[probe_eddy_current_nodrift NAME]`)

**Purpose:** Performs bed leveling using eddy current sensor

**Key Features:**
- Measures eddy current frequency
- Converts frequency to Z-height
- Performs automatic/rapid/manual probing
- Optionally applies temperature-based drift compensation

**Configuration:**
```ini
[probe_eddy_current_nodrift my_probe]
eddy_sensor_type: ldc1612
i2c_address: 0x2a
i2c_bus: i2c0a
x_offset: 0.0
y_offset: 25.0
z_offset: 2.0
```

## How They Work Together

### Without Temperature Compensation

```
Eddy Probe
├── Measures frequency
├── Converts to Z-height (calibration-based)
└── Returns Z position
```

**Use this when:**
- Temperature changes are minimal (< 5°C)
- Probe is well-thermally isolated
- Accuracy requirements are moderate

### With Temperature Compensation

```
Temperature Probe                  Eddy Probe
├── Reads sensor                   ├── Measures frequency
├── Applies smoothing              ├── Receives temperature data
└── Updates temperature data   →   ├── Applies drift correction
                                   ├── Converts to Z-height
                                   └── Returns compensated Z position
```

**How it works:**
1. Temperature probe continuously reads temperature
2. Eddy probe monitors temperature changes
3. When temperature changes, eddy probe applies automatic frequency adjustment
4. This compensation is based on a learned drift model
5. Result: Z-height remains accurate even with temperature changes

**Use this when:**
- Temperature changes are significant (> 5°C)
- Probe accuracy must be maintained across temperature range
- Heated bed or nozzle causes thermal drift
- Probing happens at different temperatures than initial setup

## Configuration Parameters

### Temperature Probe (`[temperature_probe]`)

| Parameter | Default | Type | Description |
|-----------|---------|------|-------------|
| sensor_type | *required* | string | Temperature sensor type (e.g., Generic 3950, MAX31865, AD595) |
| sensor_pin | *required* | string | MCU pin for sensor (format depends on MCU) |
| min_temperature | -273.15 | float | Minimum allowed temperature (°C) |
| max_temperature | 999999.9 | float | Maximum allowed temperature (°C) |
| smooth_time | 2.0 | float | Temperature smoothing time constant (seconds) |

### Eddy Current Probe (`[probe_eddy_current_nodrift]`)

| Parameter | Default | Type | Description |
|-----------|---------|------|-------------|
| eddy_sensor_type | ldc1612 | string | Type of eddy current sensor |
| i2c_address | 0x2a | hex | I2C address of sensor |
| i2c_bus | *required* | string | I2C bus name (e.g., i2c0a) |
| x_offset | 0.0 | float | X offset from nozzle (mm) |
| y_offset | 0.0 | float | Y offset from nozzle (mm) |
| z_offset | 0.0 | float | Z offset (mm) |
| calibrate | false | bool | Enable calibration mode |
| calibration_data | (empty) | string | Path to calibration data file |

## G-Code Commands

### Standard Probing Commands

These work as usual with the eddy probe:

```gcode
BED_MESH_CALIBRATE
BED_MESH_PROFILE LOAD=name
PROBE
G28 Z0    ; Home Z axis using probe
```

### Temperature Monitoring

Query temperature:

```gcode
; No special command - monitor via web dashboard or status
```

### Probe Calibration Commands

If calibration mode is enabled:

```gcode
PROBE_EDDY_CURRENT_CALIBRATE
PROBE_EDDY_CURRENT_FINALIZE_CALIBRATION
PROBE_EDDY_CURRENT_ESTIMATE_BACKLASH
```

## Example Configurations

### Multi-Material Printer with Temperature Compensation

```ini
[thermistor Generic 3950]
temperature1: 25.0
resistance1: 100000.0
temperature2: 150.0
resistance2: 1641.0
temperature3: 250.0
resistance3: 226.0

# Temperature probe for nozzle thermistor
[temperature_probe bed_probe]
sensor_type: Generic 3950
sensor_pin: PF5
min_temperature: 0.0
max_temperature: 300.0
smooth_time: 2.0

# Eddy probe that uses temperature for drift compensation
[probe_eddy_current_nodrift bed_probe]
eddy_sensor_type: ldc1612
i2c_address: 0x2a
i2c_bus: i2c0a
x_offset: -30.0
y_offset: 0.0
z_offset: 2.5

# Mesh configuration
[bed_mesh]
probe_count: 5,5
algorithm: bicubic
```

### Simple Setup (No Temperature)

```ini
[probe_eddy_current_nodrift default_probe]
eddy_sensor_type: ldc1612
i2c_address: 0x2a
i2c_bus: i2c0a
x_offset: 0.0
y_offset: 20.0
z_offset: 2.0

[bed_mesh]
probe_count: 3,3
```

### Multiple Probes (Different Nozzles)

```ini
# Probe for nozzle 1 (with temperature compensation)
[temperature_probe probe_1]
sensor_type: Generic 3950
sensor_pin: PF5

[probe_eddy_current_nodrift probe_1]
eddy_sensor_type: ldc1612
i2c_address: 0x2a
i2c_bus: i2c0a
x_offset: 0.0
y_offset: 0.0
z_offset: 2.5

# Probe for nozzle 2 (without temperature compensation)
[probe_eddy_current_nodrift probe_2]
eddy_sensor_type: ldc1612
i2c_address: 0x2b
i2c_bus: i2c0b
x_offset: 0.0
y_offset: 30.0
z_offset: 2.5
```

## Troubleshooting

### Temperature Probe Not Found

**Symptom:** "Warning: temperature_probe not found"

**Solution:** This is not actually an error - it's expected when you only use the eddy probe without temperature compensation. The eddy probe simply continues without drift compensation.

If you *intended* to use temperature compensation:
1. Verify you have a `[temperature_probe]` section
2. Check that both section names match exactly
3. Verify the thermistor type is valid

### Temperature Reading Stuck

**Symptom:** Temperature stays at same value, doesn't change

**Possible causes:**
1. Sensor not connected physically
2. Wrong pin configuration
3. Wrong sensor type

**Solutions:**
1. Check physical connections
2. Verify sensor pin in `printer.cfg`
3. Check that `sensor_type` matches your actual sensor
4. Look at Klipper logs for sensor errors

### Drift Compensation Not Active

**Symptom:** Probe works but doesn't compensate for temperature changes

**Possible causes:**
1. Temperature probe not configured
2. Section names don't match
3. Probe needs calibration

**Solutions:**
1. Add `[temperature_probe]` section
2. Ensure both sections have same name
3. Run calibration routine if this is new probe
4. Check that temperature sensor is actually reading

### Z-Offset Changes with Temperature

**Symptom:** Z-offset value needs adjustment at different temperatures

**Solution:** This is what drift compensation is designed to fix!

1. Configure `[temperature_probe]` section to enable temperature compensation
2. Make sure both sections have the same name
3. The probe will automatically compensate for temperature changes

If you don't want to add temperature compensation, you can:
- Improve thermal isolation of probe
- Use `BED_MESH_CALIBRATE` before each print to recalibrate at current temperature

## Performance Notes

### Temperature Smoothing

The `smooth_time` parameter controls how quickly the temperature reading updates:

- **smooth_time: 1.0** - Quick response, more noise
- **smooth_time: 2.0** - Good balance (recommended)
- **smooth_time: 5.0** - Slow response, very smooth

**Recommendation:** Start with 2.0 seconds and adjust based on how much temperature fluctuation you see.

### Probe Frequency

The eddy probe frequency is around 1-5 MHz. Higher frequency = more sensitive to height changes. Temperature changes affect frequency, which drift compensation corrects for.

### Calibration

Drift compensation is most accurate when:
- Initial calibration is done at moderate temperature
- Temperature changes during use are not extreme (> 100°C)
- Calibration is repeated at min and max expected temperatures

## Next Steps

1. **First Time Setup**
   - Add simple eddy probe configuration (Option 1)
   - Run `BED_MESH_CALIBRATE` to verify it works
   - Test probing at different locations

2. **Adding Temperature Compensation (Optional)**
   - Add `[temperature_probe]` section with same name as eddy probe
   - Verify temperature sensor is reading correctly
   - Adjust `smooth_time` if needed
   - Re-run `BED_MESH_CALIBRATE` for calibration at new temperature

3. **Optimization**
   - Observe temperature drift with `QUERY_PROBE`
   - If significant drift, increase `smooth_time`
   - If still drifting, ensure temperature sensor connection is good

## See Also

- [EDDY_PROBE_SEPARATE_CONFIG.md](EDDY_PROBE_SEPARATE_CONFIG.md) - Detailed configuration reference
- [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md) - Technical architecture details
- Klipper Documentation - For sensor types and MCU pin formats
