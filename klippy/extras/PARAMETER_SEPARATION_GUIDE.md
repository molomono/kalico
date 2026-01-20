# Configuration Parameter Separation Summary

## Overview of Changes

The `probe_eddy_current_nodrift.py` has been refactored to separate the temperature sensor and eddy current sensor configurations, eliminating conflicts caused by the shared `sensor_type` parameter.

## What Changed

### Before (Conflicting Configuration)
```ini
[probe_eddy_current_nodrift my_probe]
sensor_type: ldc1612          # ← Eddy sensor type
i2c_address: 0x2a
i2c_bus: i2c0a
min_temp: 0
max_temp: 100
smooth_time: 2.0
z_offset: 2.5
```

**Problem**: The single `sensor_type: ldc1612` conflicts with the temperature sensor configuration. There's no way to specify both the eddy sensor AND the temperature sensor type.

### After (Separated Configuration)
```ini
[probe_eddy_current_nodrift my_probe]
# Temperature sensor (standard Klipper parameters)
sensor_type: Generic 3950     # ← Temperature sensor type
sensor_pin: PA0
min_temperature: 0
max_temperature: 100
smooth_time: 2.0
horizontal_move_z: 2.0

# Eddy current sensor (dedicated parameters)
eddy_sensor_type: ldc1612     # ← Eddy sensor type
i2c_address: 0x2a
i2c_bus: i2c0a

# Probe offsets
x_offset: 0.0
y_offset: 0.0
z_offset: 2.5
```

**Solution**: Clear separation of concerns with dedicated parameters for each sensor type.

## Code Changes in probe_eddy_current_nodrift.py

### 1. InternalTemperatureSensor Class

**Changed parameter names to standard Klipper conventions:**
```python
# Before
self.min_temp = config.getfloat("min_temp", KELVIN_TO_CELSIUS, ...)
self.max_temp = config.getfloat("max_temp", 99999999.9, ...)

# After
self.min_temp = config.getfloat("min_temperature", KELVIN_TO_CELSIUS, ...)
self.max_temp = config.getfloat("max_temperature", 99999999.9, ...)
```

**Why**: Aligns with Klipper's standard `min_temperature` and `max_temperature` parameter names used in heater configs.

### 2. PrinterEddyProbeNoDrift Class

**Separated sensor type configuration:**
```python
# Before
sensors = { "ldc1612": ldc1612.LDC1612 }
sensor_type = config.getchoice('sensor_type', {s: s for s in sensors})
self.sensor_helper = sensors[sensor_type](config, self.calibration)

# After
eddy_sensors = { "ldc1612": ldc1612.LDC1612 }
eddy_sensor_type = config.getchoice('eddy_sensor_type', {s: s for s in eddy_sensors})
self.sensor_helper = eddy_sensors[eddy_sensor_type](config, self.calibration)
```

**Why**: Uses dedicated `eddy_sensor_type` parameter, allowing `sensor_type` to be used exclusively for the temperature sensor.

## Benefits of This Change

1. **No Configuration Conflicts**: Each sensor has its own `sensor_type` parameter
2. **Standard Klipper Convention**: Temperature sensor uses standard Klipper parameter names
3. **Clear Intent**: Configuration explicitly shows which parameters apply to which sensor
4. **Flexible Sensor Selection**: Can use any Klipper-supported temperature sensor type
5. **Easier Maintenance**: Parameter purposes are unambiguous

## Migration Guide

If you have an existing configuration, update it as follows:

```ini
# Old configuration
[probe_eddy_current_nodrift my_probe]
sensor_type: ldc1612
i2c_address: 0x2a
min_temp: 0
max_temp: 100
```

```ini
# New configuration
[probe_eddy_current_nodrift my_probe]
# Add temperature sensor configuration
sensor_type: Generic 3950
sensor_pin: PA0
min_temperature: 0
max_temperature: 100

# Update eddy sensor reference
eddy_sensor_type: ldc1612
i2c_address: 0x2a
```

### Parameter Name Mapping

| Old Parameter | New Parameter | Applies To | Notes |
|---------------|---------------|-----------|-------|
| `sensor_type: ldc1612` | `eddy_sensor_type: ldc1612` | Eddy Sensor | Renamed to avoid conflict |
| `sensor_type: <temp>` | `sensor_type: <temp>` | Temp Sensor | Now used exclusively for temperature |
| `min_temp` | `min_temperature` | Temp Sensor | Standard Klipper naming |
| `max_temp` | `max_temperature` | Temp Sensor | Standard Klipper naming |
| N/A | `sensor_pin` | Temp Sensor | New required parameter |
| `horizontal_move_z` | `horizontal_move_z` | Temp Sensor | Now under temperature config section |

## Configuration Examples

### Example 1: Basic Setup with Thermistor

```ini
[probe_eddy_current_nodrift probe]
# Temperature sensor - NTC 3950 thermistor
sensor_type: Generic 3950
sensor_pin: PA0
min_temperature: 0
max_temperature: 100

# Eddy current sensor - LDC1612
eddy_sensor_type: ldc1612
i2c_address: 0x2a

# Probe offsets
z_offset: 2.5
```

### Example 2: Advanced Setup with PT100

```ini
[probe_eddy_current_nodrift probe]
# Temperature sensor - PT100 RTD with MAX31865
sensor_type: MAX31865
sensor_pin: PA0
min_temperature: 0
max_temperature: 100
smooth_time: 3.0
horizontal_move_z: 2.5

# Eddy current sensor - LDC1612
eddy_sensor_type: ldc1612
i2c_address: 0x2a
i2c_bus: i2c0a

# Probe offsets
x_offset: -25.0
y_offset: -20.0
z_offset: 2.5

# Auto-generated calibration (from PROBE_EDDY_CURRENT_CALIBRATE)
calibrate: 0.0:100000.0, 0.5:98500.0, 1.0:97000.0, 1.5:95500.0, 2.0:94000.0
calibration_temp: 20.5

# Auto-generated drift compensation (from TEMPERATURE_PROBE_CALIBRATE)
drift_calibration_min_temp: 20.0
drift_calibration:
    1.234567, 0.123456, 0.001234,
    1.111111, 0.111111, 0.001111,
    1.000000, 0.100000, 0.001000,
    0.999999, 0.099999, 0.000999,
    0.888888, 0.088888, 0.000888
```

## Testing Your Configuration

After updating your configuration:

1. **Verify Syntax**: Check that Klipper can parse the config file
2. **Check Logs**: Look for any sensor initialization errors
3. **Test Temperature Sensor**: Run `M105` to check temperature readings
4. **Test Eddy Sensor**: Verify I2C communication in logs
5. **Run Calibration**: Execute probe calibration commands

### Diagnostic Commands

```gcode
# Check temperature reading
M105

# Check probe status
PROBE_STATUS

# Verify I2C sensors
[Special diagnostic commands depend on your MCU]
```

## Supported Temperature Sensor Types

The following temperature sensors are supported (standard Klipper):

- **Generic 3950**: NTC thermistor
- **Generic 3950 1%**: NTC thermistor with 1% tolerance
- **AD595**: Thermocouple with AD595 amplifier
- **AD597**: Thermocouple with AD597 amplifier
- **AD8494**: Thermocouple with AD8494 amplifier
- **AD8495**: Thermocouple with AD8495 amplifier
- **MAX6675**: Thermocouple with MAX6675 interface
- **MAX31855**: Thermocouple with MAX31855 interface
- **MAX31856**: Thermocouple with MAX31856 interface
- **MAX31865**: PT100/PT1000 RTD with MAX31865 interface
- **BME280**: Environmental sensor (temperature + pressure + humidity)
- **NTC 100K Beta 3950**: Common NTC thermistor variant

## Troubleshooting

### Error: "Unknown config option 'eddy_sensor_type'"
**Cause**: Using old version of probe_eddy_current_nodrift.py
**Solution**: Update to the latest version with separated configuration

### Error: "sensor_type not found"
**Cause**: Trying to use temperature sensor type as eddy sensor type
**Solution**: Use proper configuration structure with both sensor types specified

### Temperature readings are zero or invalid
**Cause**: Incorrect sensor_type or sensor_pin specified
**Solution**: Verify your temperature sensor model and GPIO pin match the hardware

### I2C communication errors
**Cause**: Wrong I2C bus or address for eddy sensor
**Solution**: Check `i2c_bus` and `i2c_address` parameters match your hardware setup

## Summary

The configuration parameter separation ensures:
- ✅ Clear distinction between temperature and eddy sensors
- ✅ No conflicting `sensor_type` parameters
- ✅ Alignment with Klipper conventions
- ✅ Support for any Klipper-compatible temperature sensor
- ✅ Future extensibility for additional sensors

For detailed configuration reference, see [PROBE_EDDY_CURRENT_NODRIFT_CONFIG_REFERENCE.md](PROBE_EDDY_CURRENT_NODRIFT_CONFIG_REFERENCE.md)
