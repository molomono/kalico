# Configuration Structure Visualization

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│     probe_eddy_current_nodrift Configuration Section             │
│                                                                   │
│  [probe_eddy_current_nodrift my_probe]                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────┐                         │
│  │  TEMPERATURE SENSOR SECTION        │                         │
│  ├────────────────────────────────────┤                         │
│  │ sensor_type: Generic 3950          │  ← Sensor model         │
│  │ sensor_pin: PA0                    │  ← GPIO pin             │
│  │ min_temperature: 0                 │  ← Min safe temp        │
│  │ max_temperature: 100               │  ← Max safe temp        │
│  │ smooth_time: 2.0                   │  ← Smoothing constant   │
│  │ horizontal_move_z: 2.0             │  ← Calibration Z height │
│  └────────────────────────────────────┘                         │
│                                                                   │
│  ┌────────────────────────────────────┐                         │
│  │  EDDY CURRENT SENSOR SECTION       │                         │
│  ├────────────────────────────────────┤                         │
│  │ eddy_sensor_type: ldc1612          │  ← Sensor model         │
│  │ i2c_address: 0x2a                  │  ← I2C address          │
│  │ i2c_bus: i2c0a                     │  ← I2C bus              │
│  └────────────────────────────────────┘                         │
│                                                                   │
│  ┌────────────────────────────────────┐                         │
│  │  PROBE OFFSET SECTION              │                         │
│  ├────────────────────────────────────┤                         │
│  │ x_offset: 0.0                      │  ← X offset             │
│  │ y_offset: 0.0                      │  ← Y offset             │
│  │ z_offset: 2.5                      │  ← Z offset             │
│  └────────────────────────────────────┘                         │
│                                                                   │
│  ┌────────────────────────────────────┐                         │
│  │  CALIBRATION SECTION (AUTO-GEN)    │                         │
│  ├────────────────────────────────────┤                         │
│  │ calibrate: 0.0:100000.0, ...       │  ← Z calibration       │
│  │ calibration_temp: 20.5             │  ← Cal temperature      │
│  │ drift_calibration: ...             │  ← Polynomial coeffs    │
│  │ drift_calibration_min_temp: 20.0   │  ← Min valid temp       │
│  └────────────────────────────────────┘                         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
┌──────────────────────────────────┐
│  Printer Configuration (ini)     │
│  probe_eddy_current_nodrift      │
└──────────────────┬───────────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │ Config Parser        │
        └──────────┬───────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
┌──────────────────┐  ┌──────────────────────┐
│ Temperature      │  │ Eddy Current Sensor  │
│ Sensor Config    │  │ Config               │
│                  │  │                      │
│ sensor_type      │  │ eddy_sensor_type     │
│ sensor_pin       │  │ i2c_address          │
│ min_temperature  │  │ i2c_bus              │
│ max_temperature  │  │ x_offset             │
│ smooth_time      │  │ y_offset             │
│ horizontal_move_z│  │ z_offset             │
└────────┬─────────┘  └──────────┬───────────┘
         │                       │
         ▼                       ▼
┌──────────────────┐  ┌──────────────────────┐
│ InternalTemp     │  │ EddyCalibration      │
│ Sensor           │  │                      │
│                  │  │ + Frequency to       │
│ • Smoothing      │  │   Height Mapping     │
│ • Min/Max track  │  │ + Drift Compensation │
│ • Temp callback  │  │                      │
└────────┬─────────┘  └──────────┬───────────┘
         │                       │
         ▼                       ▼
┌──────────────────────────────────────┐
│ DriftCompensationEngine              │
│                                      │
│ • Temperature tracking               │
│ • Polynomial drift models            │
│ • Frequency adjustment               │
│ • Calibration management             │
└──────────────────┬───────────────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │ Probe Operations     │
        │                      │
        │ • Z calibration      │
        │ • Probing            │
        │ • Drift compensation │
        └──────────────────────┘
```

## Configuration Separation Visualization

```
BEFORE (Conflicting):
═════════════════════════════════════════
[probe_eddy_current_nodrift probe]
sensor_type: ldc1612  ❌ Ambiguous!
             ↓
    Which sensor does this configure?
    Temperature? Eddy current?
         
         ┌─────────────────┐
         │    CONFUSION    │
         └─────────────────┘
         
i2c_address: 0x2a
min_temp: 0
max_temp: 100


AFTER (Clear):
═════════════════════════════════════════
[probe_eddy_current_nodrift probe]

# Temperature Section
sensor_type: Generic 3950  ✓ Clear: Temperature
sensor_pin: PA0
min_temperature: 0
max_temperature: 100
smooth_time: 2.0
horizontal_move_z: 2.0

# Eddy Section  
eddy_sensor_type: ldc1612  ✓ Clear: Eddy Sensor
i2c_address: 0x2a
i2c_bus: i2c0a

# Probe Section
x_offset: 0.0
y_offset: 0.0
z_offset: 2.5
```

## Parameter Organization

```
┌─────────────────────────────────────────────────────┐
│        probe_eddy_current_nodrift Parameters        │
├─────────────────────────────────────────────────────┤
│                                                     │
│  TEMPERATURE SENSOR GROUP                          │
│  ├─ sensor_type (required)                          │
│  ├─ sensor_pin (required)                           │
│  ├─ min_temperature (optional)                      │
│  ├─ max_temperature (optional)                      │
│  ├─ smooth_time (optional)                          │
│  └─ horizontal_move_z (optional)                    │
│                                                     │
│  EDDY CURRENT SENSOR GROUP                         │
│  ├─ eddy_sensor_type (required)                     │
│  ├─ i2c_address (required)                          │
│  ├─ i2c_bus (required)                              │
│  ├─ x_offset (optional)                             │
│  ├─ y_offset (optional)                             │
│  └─ z_offset (optional)                             │
│                                                     │
│  CALIBRATION GROUP (AUTO-GENERATED)                │
│  ├─ calibrate                                       │
│  ├─ calibration_temp                                │
│  ├─ drift_calibration                               │
│  ├─ drift_calibration_min_temp                      │
│  └─ max_validation_temp                             │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Configuration Workflow

```
START: Empty printer.cfg
   │
   ▼
STEP 1: Add Minimal Configuration
┌────────────────────────────────┐
│ [probe_eddy_current_nodrift]   │
│ sensor_type: Generic 3950      │ ← Temperature
│ sensor_pin: PA0                │
│ eddy_sensor_type: ldc1612      │ ← Eddy
│ i2c_address: 0x2a             │
│ z_offset: 2.5                  │
└────────────────────────────────┘
   │
   ▼
STEP 2: Run Z Calibration
Command: PROBE_EDDY_CURRENT_CALIBRATE
   │
   ▼
STEP 3: Config Updated with Calibration
┌────────────────────────────────┐
│ ... (from step 1)              │
│ calibrate: 0.0:100000.0, ...   │ ← Added
│ calibration_temp: 20.5         │ ← Added
└────────────────────────────────┘
   │
   ▼
STEP 4: Run Drift Calibration
Command: TEMPERATURE_PROBE_CALIBRATE TARGET=80
   │
   ▼
STEP 5: Config Updated with Drift Data
┌────────────────────────────────┐
│ ... (from step 3)              │
│ drift_calibration:             │ ← Added
│    1.234, 0.123, 0.001,        │
│    1.111, 0.111, 0.001, ...    │
│ drift_calibration_min_temp: 20 │ ← Added
└────────────────────────────────┘
   │
   ▼
COMPLETE: Ready for operation
```

## Parameter Type Reference

```
STRING PARAMETERS:
├─ sensor_type: "Generic 3950", "MAX31865", "AD595", etc.
├─ eddy_sensor_type: "ldc1612"
├─ sensor_pin: "PA0", "PB1", etc.
├─ i2c_bus: "i2c0a", "i2c1a", etc.
└─ calibrate: "0.0:100000.0, 1.0:95000.0, ..."

FLOAT PARAMETERS:
├─ min_temperature: 0.0
├─ max_temperature: 100.0
├─ smooth_time: 2.0
├─ horizontal_move_z: 2.0
├─ x_offset: 0.0
├─ y_offset: 0.0
├─ z_offset: 2.5
└─ calibration_temp: 20.5

HEX PARAMETERS:
└─ i2c_address: 0x2a, 0x2b, etc.

LIST PARAMETERS:
└─ drift_calibration: [1.234, 0.123, 0.001], [...]
```

## Sensor Support Matrix

```
TEMPERATURE SENSORS (sensor_type parameter):
├─ NTC Thermistors
│  ├─ Generic 3950
│  ├─ Generic 3950 1%
│  └─ NTC 100K Beta 3950
├─ RTD Sensors
│  └─ MAX31865 (PT100, PT1000)
├─ Thermocouple Sensors
│  ├─ AD595
│  ├─ AD597
│  ├─ AD8494
│  ├─ AD8495
│  ├─ MAX6675
│  ├─ MAX31855
│  └─ MAX31856
└─ Environmental Sensors
   └─ BME280 (+ pressure, humidity)

EDDY CURRENT SENSORS (eddy_sensor_type parameter):
└─ ldc1612
   └─ Expandable for future sensors
```

## Configuration Validation Flow

```
┌──────────────────────┐
│ Parse printer.cfg    │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────┐
│ Validate Temperature Sensor       │
├──────────────────────────────────┤
│ ✓ sensor_type provided?           │
│ ✓ sensor_pin provided?            │
│ ✓ sensor_type is valid?           │
│ ✓ min_temp < max_temp?            │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│ Validate Eddy Current Sensor      │
├──────────────────────────────────┤
│ ✓ eddy_sensor_type provided?      │
│ ✓ i2c_address provided?           │
│ ✓ eddy_sensor_type is valid?      │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│ Validate Calibration (if present) │
├──────────────────────────────────┤
│ ✓ calibrate format valid?         │
│ ✓ drift_calibration coefficients? │
│ ✓ Polynomial validity?            │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────┐
│ Configuration Valid  │
│ Proceed with Setup   │
└──────────────────────┘
```

## Summary Table

| Aspect | Before | After |
|--------|--------|-------|
| **sensor_type usage** | Ambiguous (both sensors) | Clear (temp only) |
| **Eddy config** | In sensor_type | In eddy_sensor_type |
| **Temp config** | Incomplete | Complete |
| **Parameter names** | Non-standard | Klipper-standard |
| **Temperature sensors** | Not supported | All Klipper types |
| **Documentation** | Minimal | Comprehensive |
| **Clarity** | Low | High |
| **Extensibility** | Limited | Full |

---

**Visual documentation complete. Configuration structure is now clear and unambiguous.**
