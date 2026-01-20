# Configuration Parameter Reference

## Temperature Sensor vs Eddy Current Sensor Parameters

This document clarifies how the temperature sensor and eddy current sensor parameters are now separated to avoid conflicts.

## Temperature Sensor Parameters (Standard Klipper)

The temperature sensor uses standard Klipper sensor configuration parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sensor_type` | string | Required | Temperature sensor type (Generic 3950, MAX31865, AD595, PT100RTD, PT1000, etc.) |
| `sensor_pin` | string | Required | GPIO pin for sensor input |
| `min_temperature` | float | -273.15 | Minimum safe operating temperature (°C) |
| `max_temperature` | float | 350 | Maximum safe operating temperature (°C) |
| `smooth_time` | float | 2.0 | Temperature smoothing time constant (seconds) |
| `horizontal_move_z` | float | 2.0 | Z height for horizontal moves during calibration (mm) |

### Temperature Sensor Type Examples

```ini
# NTC 3950 thermistor (most common)
sensor_type: Generic 3950
sensor_pin: PA0

# PT100 RTD sensor with MAX31865 converter
sensor_type: MAX31865
sensor_pin: PA0

# Thermocouple with AD595 amplifier
sensor_type: AD595
sensor_pin: PA0

# Silicon-based sensor
sensor_type: BME280
i2c_address: 0x77
```

## Eddy Current Sensor Parameters

The eddy current sensor uses dedicated parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `eddy_sensor_type` | string | Required | Eddy sensor type (ldc1612) |
| `i2c_address` | hex | 0x2a | I2C address of the eddy sensor |
| `i2c_bus` | string | Required | I2C bus identifier (e.g., i2c0a, i2c1a) |
| `x_offset` | float | 0.0 | X offset from nozzle to sensor (mm) |
| `y_offset` | float | 0.0 | Y offset from nozzle to sensor (mm) |
| `z_offset` | float | 0.0 | Z offset from nozzle to sensor (mm) |

### Eddy Sensor Type Examples

```ini
# LDC1612 eddy current sensor (current implementation)
eddy_sensor_type: ldc1612
i2c_address: 0x2a
i2c_bus: i2c0a
```

## Shared Probe Parameters

These parameters apply to the overall probe behavior and are auto-generated during calibration:

| Parameter | Type | Description |
|-----------|------|-------------|
| `calibrate` | string | Frequency-to-height mapping from Z calibration (auto-generated) |
| `calibration_temp` | float | Temperature at which Z offset calibration was performed |
| `drift_calibration` | list | Polynomial coefficients for temperature drift compensation |
| `drift_calibration_min_temp` | float | Minimum temperature for drift calibration validity |
| `max_validation_temp` | float | Maximum temperature for drift validation |

## Example Configurations

### Minimal Configuration

```ini
[probe_eddy_current_nodrift my_probe]
# Temperature sensor
sensor_type: Generic 3950
sensor_pin: PA0

# Eddy current sensor
eddy_sensor_type: ldc1612
i2c_address: 0x2a

# Probe offset
z_offset: 2.5
```

### Complete Configuration

```ini
[probe_eddy_current_nodrift my_probe]
# Temperature sensor configuration (standard Klipper)
sensor_type: Generic 3950
sensor_pin: PA0
min_temperature: 0
max_temperature: 100
smooth_time: 2.0
horizontal_move_z: 2.0

# Eddy current sensor configuration
eddy_sensor_type: ldc1612
i2c_address: 0x2a
i2c_bus: i2c0a

# Probe offset configuration
x_offset: -25.0
y_offset: -20.0
z_offset: 2.5

# Calibration data (auto-generated)
calibrate: 0.0:100000.0, 0.5:98500.0, 1.0:97000.0, 1.5:95500.0, 2.0:94000.0

# Drift compensation (auto-generated during calibration)
calibration_temp: 20.5
drift_calibration_min_temp: 20.0
max_validation_temp: 60.0
drift_calibration:
    1.234567, 0.123456, 0.001234,
    1.234567, 0.123456, 0.001234,
    1.234567, 0.123456, 0.001234
```

## Configuration Flow

### 1. Initial Setup

Start with minimal temperature and eddy sensor parameters:

```ini
[probe_eddy_current_nodrift my_probe]
sensor_type: Generic 3950
sensor_pin: PA0
eddy_sensor_type: ldc1612
i2c_address: 0x2a
z_offset: 0.0
```

### 2. After Z Calibration

After running `PROBE_EDDY_CURRENT_CALIBRATE`:

```ini
[probe_eddy_current_nodrift my_probe]
# ... sensor config ...
calibrate: 0.0:100000.0, 1.0:95000.0, ...
calibration_temp: 20.5
```

### 3. After Drift Compensation Calibration

After running `TEMPERATURE_PROBE_CALIBRATE TARGET=80`:

```ini
[probe_eddy_current_nodrift my_probe]
# ... sensor config ...
calibrate: ...
calibration_temp: 20.5
drift_calibration_min_temp: 20.0
drift_calibration:
    1.234567, 0.123456, 0.001234,
    ...
```

## Sensor Selection Guide

### Temperature Sensor Type Selection

**Use case: NTC Thermistor (Generic 3950)**
- Most affordable
- Adequate accuracy for general use
- Good for non-critical applications
- Requires voltage divider circuit

**Use case: PT100 RTD + MAX31865**
- Better accuracy and stability
- Industrial standard
- Good temperature range
- Requires MAX31865 converter module

**Use case: Thermocouple + AD595**
- Very wide temperature range
- Fast response time
- Lower accuracy than PT100
- Good for extreme temperature environments

### Eddy Sensor Type Selection

**Current Implementation: LDC1612**
- I2C interface
- Non-contact measurement
- Good for Z-probe applications
- Supports up to 16 sensors on same I2C bus (different addresses)

## Troubleshooting Configuration Issues

### Problem: "sensor_type not found"
**Cause**: Using single `sensor_type` for eddy sensor
**Solution**: Use `eddy_sensor_type: ldc1612` instead

### Problem: Temperature readings are 0 or invalid
**Cause**: Wrong temperature sensor type specified
**Solution**: Verify `sensor_type` matches actual sensor hardware

### Problem: I2C communication errors
**Cause**: Incorrect I2C bus or address
**Solution**: Verify `i2c_bus` and `i2c_address` match hardware setup

### Problem: Probe offset errors
**Cause**: Using temperature sensor parameter names for probe offsets
**Solution**: Use dedicated `x_offset`, `y_offset`, `z_offset` parameters

## Configuration Validation

The system validates configuration on startup:

1. **Temperature Sensor**: Must have `sensor_type` and `sensor_pin`
2. **Eddy Sensor**: Must have `eddy_sensor_type` and `i2c_address`
3. **Drift Calibration**: Must have valid polynomial coefficients if specified
4. **Z Calibration**: Must have frequency-to-height mapping if drift calibration exists

Invalid configurations will be reported in logs with diagnostic information.
