# Temperature Probe Quick Reference

## Installation

1. Add `temperature_probe.py` to `kalico/klippy/extras/`
2. Add configuration section to `printer.cfg`
3. Ensure `[probe_eddy_current]` section exists with matching name

## Basic Configuration

```ini
[temperature_probe btt_eddy]
sensor_type: Generic 3950
sensor_pin: eddy:gpio26
```

## With Drift Compensation (Recommended)

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
calibration_position: 150, 150, 20
calibration_bed_temp: 65
calibration_extruder_temp: 240

[probe_eddy_current btt_eddy]
# ... existing probe configuration
```

## Key G-Code Commands

### Start Calibration
```gcode
G28                                           ; Home printer
TEMPERATURE_PROBE_CALIBRATE PROBE=btt_eddy TARGET=60 STEP=2
```

### During Calibration
```gcode
TEMPERATURE_PROBE_NEXT       ; Go to next sample (automatic)
TEMPERATURE_PROBE_COMPLETE   ; Finish if done
ABORT                        ; Cancel calibration
```

### Enable/Disable Compensation
```gcode
TEMPERATURE_PROBE_ENABLE PROBE=btt_eddy ENABLE=1   ; On
TEMPERATURE_PROBE_ENABLE PROBE=btt_eddy ENABLE=0   ; Off
```

### Check Status
```gcode
QUERY_PROBE PROBE=btt_eddy
```

## Configuration Parameters Quick Lookup

| Parameter | Purpose | Default |
|-----------|---------|---------|
| sensor_type | Temperature sensor model | Required |
| sensor_pin | MCU pin for sensor | Required |
| smooth_time | Noise reduction (seconds) | 2.0 |
| calibration_position | Where to probe (X, Y, Z) | None |
| calibration_bed_temp | Target bed temp (°C) | None |
| calibration_extruder_temp | Target hotend temp (°C) | None |

## Understanding Drift Compensation

**Problem:** Eddy probe frequency changes with temperature

**Solution:** Store how frequency changes at different Z heights vs temperature

**Implementation:** Uses 9 polynomial models (one per Z sample)

**Benefit:** Automatic correction - Z offset stays accurate across temperature range

## Temperature Sensor Types

Common options:

| Type | Pin Format | Notes |
|------|-----------|-------|
| Generic 3950 | `eddy:gpio26` | NTC thermistor (most common) |
| MAX31865 | SPI pins | PT100 RTD sensor |
| AD595 | Analog pin | K-type thermocouple |

## Troubleshooting Summary

| Issue | Check |
|-------|-------|
| Temperature stuck at 0 | Sensor connection, sensor_pin, thermistor type |
| Won't link with probe | Section names must match exactly |
| Calibration fails | Printer must be homed, enough temperature range |
| Weird readings | Try increasing smooth_time |

## File Structure

```
kalico/
├── klippy/
│   └── extras/
│       └── temperature_probe.py          # New module
└── docs/
    └── Temperature_Probe.md              # Documentation
```

## Key Classes

```python
TemperatureProbe              # Main temperature sensor handler
├─ _temp_callback()          # Temperature reading handler
├─ cmd_TEMPERATURE_PROBE_CALIBRATE()    # Start calibration
└─ get_status()              # Return temperature status

EddyDriftCompensation        # Drift compensation model
├─ collect_sample()          # Sample during calibration
├─ adjust_freq()             # Correct measured frequency
└─ finish_calibration()      # Save polynomial coefficients

Polynomial2d                  # Curve fitting utility
├─ __call__()                # Evaluate polynomial
└─ fit()                      # Fit to data points
```

## Common Configuration Examples

### Voron 2.4 with BTT Eddy
```ini
[temperature_probe btt_eddy]
sensor_type: Generic 3950
sensor_pin: eddy:gpio26
calibration_position: 175, 175, 20
calibration_bed_temp: 60
calibration_extruder_temp: 220
```

### Voron Trident with BTT Eddy
```ini
[temperature_probe btt_eddy]
sensor_type: Generic 3950
sensor_pin: eddy:gpio26
calibration_position: 150, 150, 20
calibration_bed_temp: 65
calibration_extruder_temp: 250
```

### Bamboo Lab P1 with BTT Eddy Coil
```ini
[temperature_probe btt_eddy]
sensor_type: Generic 3950
sensor_pin: mcu:gpio23
calibration_position: 125, 125, 20
calibration_bed_temp: 50
calibration_extruder_temp: 245
```

## Performance Tips

1. **Reduce noise:** Increase `smooth_time` (2.0-5.0 seconds)
2. **Faster response:** Decrease `smooth_time` (1.0-2.0 seconds)
3. **Better calibration:** Use smaller STEP value (1.0-2.0°C)
4. **Wider range:** Calibrate from 20°C to 70°C for bed sensors
5. **Save results:** Always run `SAVE_CONFIG` after calibration

## Integration Checklist

- [ ] Add `temperature_probe.py` to `kalico/klippy/extras/`
- [ ] Define thermistor type in `printer.cfg`
- [ ] Add `[temperature_probe]` section with matching probe name
- [ ] Verify sensor_pin is correct
- [ ] Test with `QUERY_PROBE PROBE=name`
- [ ] Run `TEMPERATURE_PROBE_CALIBRATE` when ready
- [ ] Save configuration with `SAVE_CONFIG`

## References

- **Klipper Probe Calibrate:** https://www.klipper3d.org/Probe_Calibrate.html
- **Temperature Sensors:** https://www.klipper3d.org/Config_Reference.html#thermistors
- **G-Code:** https://www.klipper3d.org/G-Codes.html

## Support

For issues or questions:
1. Check logs for errors: `journalctl -u klipper -f`
2. Review configuration syntax
3. Test manually with G-Code commands
4. Check Kalico/Klipper community forums
