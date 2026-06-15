# Contributing

Thanks for helping grow MikeScript Gamepad! The goal is simple: let anyone use a
flight-sim HOTAS in any game that takes an Xbox controller, and make it easy to
share working setups.

## The easiest contribution: a profile

If you got your stick working for a game, share the mapping so the next person
doesn't have to start from scratch.

1. In the GUI, set up your device and game, then **Save Profile**.
2. Copy your saved JSON to `profiles/<game>_<device>.json`
   (e.g. `profiles/fivem_logitech_x52.json`).
3. Give it a clear `"name"` and a `"device_name_contains"` hint.
4. Open a pull request. That's it — the app auto-discovers it.

See [docs/PROFILE_SCHEMA.md](docs/PROFILE_SCHEMA.md) for every field.

Please include in the PR description: your exact device, the game, the axis
mode/quirks (e.g. "Hotas One in 5/8 mode, twist unlocked"), and anything that
tripped you up.

## Code contributions

The codebase is small and layered so it's easy to extend:

| File | Responsibility |
|------|----------------|
| `app/bridge/input.py`   | Read the HOTAS (pygame). |
| `app/bridge/output.py`  | The virtual pad (vgamepad/ViGEmBus) + button table. |
| `app/bridge/curves.py`  | Deadzone / expo / invert / calibration math. |
| `app/bridge/mapper.py`  | **The one place** raw input becomes a pad state. |
| `app/bridge/library.py` | Mappable outputs, profile discovery, brand detection. |
| `app/bridge/engine.py`  | Headless run loop (CLI). |
| `app/gui.py`            | The graphical app. |
| `app/run.py`            | CLI entry (`list/monitor/setup/calibrate/bind/run`). |

Good first issues / ideas that fit the architecture:

- **New output device** (e.g. DualShock 4): add a `VDS4Gamepad` path in
  `output.py` and a `output` field to the profile. The mapper is unaffected.
- **More games**: ship profiles + a short notes file. No code needed.
- **New input backends** (e.g. raw HID for sticks SDL mislabels): implement the
  same `poll() -> (axes, buttons, hats)` shape as `input.py`.
- **Per-axis curves in the GUI**: expose `deadzone`/`expo`/`sensitivity` sliders
  (the profile and mapper already support them).

### Ground rules

- Keep `mapper.py` the single source of truth — don't duplicate mapping logic.
- Pure logic (curves, library, mapper) should stay unit-testable without
  hardware, a display, or the ViGEmBus driver.
- Don't break `list`/`monitor`/the GUI's read-only mode working without the
  driver installed.

Adding a brand: extend `KNOWN_BRANDS` in `app/bridge/library.py` and (optionally)
drop a starter profile in `profiles/` with a matching `device_name_contains`.

## Running from source

```
pip install -r app/requirements.txt
python app/gui.py            # GUI
python app/run.py monitor    # CLI live view
```
