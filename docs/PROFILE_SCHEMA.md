# Profile schema

A profile is a JSON file in [`profiles/`](../profiles/). Every file there is
auto-discovered and shown in the GUI's **Profile** dropdown — adding support for
a new HOTAS or a new game is just adding a file. No code changes.

```jsonc
{
  "name": "FiveM / GTA V - My Stick (Flight)",   // shown in the GUI dropdown
  "device_name_contains": "Hotas",                // auto-pick a device by name (optional)
  "update_rate_hz": 120,                          // poll/output rate

  // OPTIONAL multi-device: one entry per device "slot". Mappings reference a
  // slot with their "device" field (default 0). Matched to a connected
  // controller by name, so a separate stick + throttle + pedals all merge.
  "devices": [
    { "name_contains": "Stick" },     // slot 0
    { "name_contains": "Throttle" },  // slot 1
    { "name_contains": "Rudder" }     // slot 2
  ],

  "axes": [                                        // physical axis -> stick/trigger
    {
      "source": 0,            // axis index on its device (see the live view / monitor)
      "device": 0,            // which device slot (default 0)
      "target": "LEFT_X",     // LEFT_X LEFT_Y RIGHT_X RIGHT_Y LT RT RT_LT_SPLIT
      "invert": false,
      "deadzone": 0.06,       // 0..1, ignore jitter near centre
      "expo": 0.2,            // 0 linear .. 1 very soft near centre
      "sensitivity": 1.0,
      "min": -1.0,            // calibration: raw value at one extreme
      "max":  1.0             // calibration: raw value at the other extreme
      // "comment": "free text — ignored by the loader, kept for humans"
    }
  ],

  "axis_buttons": [            // an analog axis -> two digital buttons
    {
      "source": 3,
      "negative": "LB",        // pressed when (axis - rest) <= -threshold
      "positive": "RB",        // pressed when (axis - rest) >= +threshold
      "threshold": 0.5,
      "invert": false
    }
  ],

  "buttons": [                 // physical button -> pad button / full trigger
    { "source": 0, "target": "A" }
    // targets: A B X Y LB RB LS RS BACK START GUIDE
    //          DPAD_UP DPAD_DOWN DPAD_LEFT DPAD_RIGHT
    //          LT_FULL RT_FULL   (slam a trigger from a button)
  ],

  "hats": [                    // POV hat -> D-pad
    { "source": 0, "target": "DPAD" }
  ]
}
```

## Notes

- **Indices are device-specific.** Use the GUI's live panel (or `run.py
  monitor`) to see which `source` number each control is.
- **Multiple controllers:** add a `devices` list and put `"device": N` on any
  mapping to read it from slot N. Omit `devices` (and `device`) for a normal
  single-controller setup. `run.py` honours device slots; the GUI mapping screen
  currently focuses on slot 0.
- **The engine auto-zeros at startup**, and `axis_buttons` subtract the resting
  position before comparing to `threshold`, so an off-centre axis can't hold a
  button down forever.
- **Triggers** (`LT`/`RT`) map a full `min..max` axis range to `0..1`. The GUI
  auto-ranges these from the travel it sees (and uses the resting position to
  pick the idle end, so the throttle never reads inverted) — sweep it once.
- **`RT_LT_SPLIT`** turns *one* lever into both triggers: centre = neutral,
  push = `RT` (gas), pull = `LT` (brake/reverse). Best for a throttle that rests
  in the **middle** (centre-detent/self-centring). For a lever that rests at one
  end, use `RT` for gas and a **button → `LT_FULL`** for brake/back-up instead.
- Unknown keys (like `comment`) are ignored, so annotate freely.

See [CONTRIBUTING.md](CONTRIBUTING.md) to share a profile with others.
