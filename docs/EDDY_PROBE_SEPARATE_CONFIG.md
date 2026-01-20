# Separated Temperature and Eddy Probe Configuration

## Overview

The `probe_eddy_current_nodrift` module now uses **two separate configuration sections** that can optionally work together:

1. **`[temperature_probe]`** - Temperature sensing with optional drift calibration
2. **`[probe_eddy_current_nodrift]`** - Eddy current probe with optional temperature linking

This separation follows Klipper's design philosophy of modular, independent components while allowing optional integration when needed.

## Configuration Sections

### Option 1: Eddy Probe WITHOUT Temperature Compensation

Simply configure the eddy probe without any temperature section:

```ini
[probe_eddy_current_nodrift eddy_probe]
eddy_sensor_type: ldc1612
i2c_address: 0x2a
i2c_bus: i2c0a
x_offset: 0.0
y_offset: 25.0
z_offset: 2.0
```

**Use this when:**
- Temperature changes are minimal
- Drift compensation is not needed
- You want the simplest configuration

### Option 2: With Temperature-Based Drift Compensation

Configure both sections with matching names to enable drift compensation:

```ini
[thermistor Generic 3950]
temperature1: 25.0
resistance1: 100000.0
temperature2: 150.0
resistance2: 1641.0
temperature3: 250.0
resistance3: 226.0

[temperature_probe eddy_probe]
sensor_type: Generic 3950
sensor_pin: PF5
min_temperature: 0.0
max_temperature: 300.0
smooth_time: 2.0

[probe_eddy_current_nodrift eddy_probe]
eddy_sensor_type: ldc1612
i2c_address: 0x2a
i2c_bus: i2c0a
x_offset: 0.0
y_offset: 25.0
z_offset: 2.0
```

**Important:** Both sections must have the **same name** (in this example, `eddy_probe`) to be automatically linked.

## How It Works

### Automatic Linking

When Klipper loads the configuration, the eddy probe module:

1. Looks for a `[temperature_probe]` section with the same name
2. If found, creates a `DriftCompensationEngine` using the temperature sensor
3. If not found, the eddy probe works without drift compensation

### Temperature Probe Status

The `[temperature_probe]` section provides:

- **Smoothed temperature readings** - Temperature is averaged using configurable smoothing time
- **Min/max tracking** - Monitors minimum and maximum temperatures seen
- **Registration with Klipper heaters** - Integrates with the standard heater temperature monitoring system

### Optional Drift Compensation

When linked, the eddy probe:

1. Receives temperature readings from the temperature probe
2. Maintains a polynomial drift model relating temperature to probe frequency drift
3. Automatically adjusts frequency measurements to account for temperature changes
4. Improves Z-offset accuracy across the full temperature range

## Configuration Parameters

### `[temperature_probe NAME]`

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `sensor_type` | Required | - | Klipper temperature sensor type (e.g., Generic 3950, MAX31865, AD595) |
| `sensor_pin` | Required | - | MCU pin connected to the sensor |
| `min_temperature` | -273.15 | > -273.15 | Minimum allowed temperature (°C) |
| `max_temperature` | 999999.9 | > min_temperature | Maximum allowed temperature (°C) |
| `smooth_time` | 2.0 | > 0 | Temperature smoothing time constant (seconds) |

**Notes:**
- `sensor_type` must be a valid Klipper thermistor type
- `sensor_pin` format depends on your MCU (e.g., `PF5`, `PA0:pin_1`)
- `smooth_time` of 2.0 seconds provides gentle smoothing without lag

### `[probe_eddy_current_nodrift NAME]`

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `eddy_sensor_type` | ldc1612 | ldc1612 | Eddy current sensor type |
| `i2c_address` | 0x2a | 0x00-0xff | I2C address of the sensor |
| `i2c_bus` | Required | - | I2C bus name (e.g., i2c0a, i2c1) |
| `x_offset` | 0.0 | - | X offset from nozzle (mm) |
| `y_offset` | 0.0 | - | Y offset from nozzle (mm) |
| `z_offset` | 0.0 | > 0 | Z offset from probe trigger point (mm) |
| `calibrate` | false | true/false | Enable calibration mode |
| `calibration_data` | - | - | Path to saved calibration data file |

## Linking Behavior

### Matching Names

The linking is based on the **configuration section name**:

```ini
[temperature_probe probe_a]      # Name: "probe_a"
[probe_eddy_current_nodrift probe_a]  # Name: "probe_a" - LINKED
```

### Multiple Probes

You can have multiple independent probes:

```ini
# First probe with temperature compensation
[temperature_probe eddy_1]
sensor_type: Generic 3950
sensor_pin: PF5

[probe_eddy_current_nodrift eddy_1]
i2c_address: 0x2a
i2c_bus: i2c0a

# Second probe without temperature compensation
[probe_eddy_current_nodrift eddy_2]
i2c_address: 0x2b
i2c_bus: i2c0b
```

## Runtime Behavior

### Status Information

Query probe status using the `QUERY_PROBE` or similar commands:

```gcode
; Get status (if temperature-linked)
; Output includes: temperature, measured_min_temp, measured_max_temp, drift_compensation_enabled
QUERY_PROBE probe=eddy_probe
```

### Manual Temperature Override

If needed, you can temporarily disable drift compensation by removing the temperature section and restarting Klipper. The eddy probe will continue to work normally without it.

## Troubleshooting

### "temperature_probe not found"

The eddy probe silently continues without drift compensation if the temperature probe is not configured. This is intentional - no error occurs.

If you intended to use drift compensation:
1. Verify both sections have the **exact same name**
2. Check that the thermistor type is valid for your Klipper configuration
3. Verify the sensor pin is correct and available

### Temperature Reading Issues

If temperature readings seem stuck or incorrect:
1. Check the physical connection of the temperature sensor
2. Verify `sensor_type` matches your actual sensor
3. Check that `min_temperature` and `max_temperature` bounds are reasonable
4. Try adjusting `smooth_time` (larger = more smoothing, slower response)

### Drift Compensation Not Activating

Drift compensation requires:
1. Both `[temperature_probe]` and `[probe_eddy_current_nodrift]` sections
2. Matching section names
3. The temperature sensor to be physically connected and reporting values
4. Calibration data to be available (from a prior calibration run)

## Migration from Combined Configuration

If upgrading from an older version that used a combined section:

**Old (no longer supported):**
```ini
[probe_eddy_current_nodrift eddy]
sensor_type: Generic 3950          # Was in single section
sensor_pin: PF5
eddy_sensor_type: ldc1612          # Was in single section
i2c_address: 0x2a
```

**New (separated):**
```ini
[temperature_probe eddy]
sensor_type: Generic 3950          # Now in separate section
sensor_pin: PF5

[probe_eddy_current_nodrift eddy]
eddy_sensor_type: ldc1612          # Only eddy parameters here
i2c_address: 0x2a
```

## Summary

This two-section approach provides:

- **Flexibility** - Use eddy probe alone or with temperature compensation
- **Standards Compliance** - Follows Klipper's modular design principles
- **Clarity** - Each section has a single, focused responsibility
- **Maintainability** - Easier to understand and debug
- **Extensibility** - Future enhancements can extend either module independently
