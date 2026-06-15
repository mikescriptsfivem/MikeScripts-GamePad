# 🕹️ MikeScript Gamepad

**Use any joystick, HOTAS, or throttle as an Xbox controller — in any game.**

Lots of games (FiveM / GTA V, racing and flight games, etc.) read an **Xbox
controller** but ignore flight-sim joysticks. MikeScript Gamepad sits in the middle:
it reads your stick and feeds the game a **virtual Xbox controller**, with a
simple app to map your controls however you like.

### Works with your gear

Any DirectInput/XInput controller works. These brands are auto-recognised (the
app shows the name when you plug in), and several have ready-made profiles:

> **Thrustmaster · Logitech / Saitek · Turtle Beach · VKB · VIRPIL · Honeycomb ·
> WINWING · MOZA · CH Products · 8BitDo · generic sticks**

…and **multiple controllers at once** — a separate stick + throttle + rudder
pedals, even mixed brands, all merge into one virtual pad.

Don't see a ready profile for your stick? Just hit **✨ Auto-map** — it works on
anything.

- ✅ Free and open source (MIT)
- ✅ One-click setup, no coding
- ✅ Live mapping screen — see every axis & button react
- ✅ Save & share your setups as simple profile files

---

## 🚀 Quick start

1. **Double-click `Install.bat`** once. It installs Python, the driver
   (ViGEmBus), and the needed packages. Click **Yes** on any Windows prompts.
2. **Plug in your joystick**, then **double-click `MikeScript-Gamepad.bat`**.
3. In the app: pick your **Device** → click **✨ Auto-map** → **sweep the
   throttle once** → **▶ Start Bridge**. That's it — go play.

> First time mapping? Move a control and watch the **LIVE INPUT** panel light
> up — that tells you which axis/button is which.

---

## 🎮 Using the app

| Control | What it does |
|--------|---------------|
| **Device** | Pick the controller to read. |
| **LIVE INPUT** | Move the stick / press buttons and watch them react — your proof it's registering. |
| **MAPPING** | Choose which physical axis/button drives each output (roll, pitch, throttle, yaw, buttons…). |
| **✨ Auto-map** | Instantly lays out a sensible default for *any* stick. Start here. |
| **▶ Start Bridge** | Goes live — the game now sees an Xbox controller. |
| **💾 Save Profile** | Saves your mapping so you don't redo it. |

### Throttle, brake & reverse / backing up

- **Throttle → RT** = accelerate. The app uses your throttle's resting position
  to figure out which end is idle, so it won't read backwards. If it ever feels
  reversed, tick **invert** on that row.
- **Brake / reverse / back up → a button mapped to LT.** In GTA, LT is brake
  *and* reverse: tap to brake, hold to back up. Auto-map puts this on button 0.
- **Want gas + reverse on the lever itself?** Set the throttle row to
  **"Throttle+reverse"** — push = gas, pull = reverse. Best for throttles that
  rest in the **middle**; for a lever that rests at one end, use the button above.

---

## 🧩 Multiple controllers (stick + throttle + pedals)

MikeScript Gamepad can merge several devices into one virtual pad — perfect for a
separate throttle quadrant or rudder pedals, even from different brands. Each
mapping has a `device` slot, and the profile's `devices` list names the
controller behind each slot. See **[docs/PROFILE_SCHEMA.md](docs/PROFILE_SCHEMA.md)**
for the format. (The app's mapping screen focuses on a single device; multi-
device profiles are set up in the JSON file today.)

---

## 🌍 Share your setup & help others

Got your stick working? **Save Profile**, then drop the JSON into
[`profiles/`](profiles/) and send a pull request — the app auto-discovers every
profile in that folder, so others with your gear get it for free.

- [`profiles/template.json`](profiles/template.json) — copy this to start.
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) — share profiles or extend the code.

---

## ❓ Troubleshooting

- **App says "no devices"** — plug the stick in (set the Hotas One switch to
  PC/Xbox mode), then click ↻ Refresh.
- **"couldn't open a virtual controller"** — the ViGEmBus driver isn't
  installed/running. Run `Install.bat` again and reboot.
- **A control is reversed** — tick **invert** on its row.
- **It drifts / turns on its own** — an axis rests off-centre; the app
  auto-zeros at start, so just don't touch the stick for a second when it
  begins. Re-pick the device if needed.
- **The game sees double inputs** — some sticks (like the Hotas One) also show
  up as an Xbox controller, so the game sees both it and the virtual one. Install
  **[HidHide](https://github.com/nefarius/HidHide/releases)** and hide the
  physical device from the game (this app still reads it).

---

## 🔧 How it works

```
Your joystick(s)
   │  read raw axes / buttons / hats (pygame / SDL)
   ▼
Mapping + curves   (deadzone · expo · invert · calibration — your profile)
   ▼
Virtual Xbox 360 controller   (ViGEmBus driver, via vgamepad)
   ▼
The game
```

The game just sees a normal Xbox pad. All mapping flows through one module
([`bridge/mapper.py`](bridge/mapper.py)) so the app and the command line behave
identically.

---

## ⚖️ Fair play

This is an **input remapper** — the same idea as reWASD, JoyToKey, or Steam
Input. It only translates *your* inputs into controller inputs; it does **not**
automate aiming, firing, or driving. Online servers set their own rules, so
don't pair it with anything that plays the game for you.

---

## 📁 What's in the folder

```
MikeScript-Gamepad.bat   ← double-click to launch the app
Install.bat        ← run once to set everything up
README.md  LICENSE
app/               ← the program (you don't need to open this)
profiles/          ← saved controller setups (yours + bundled)
docs/              ← profile format + contributing guide
```

## 🛠️ Advanced (command line)

Prefer a terminal? `python app\run.py monitor` shows live input,
`python app\run.py run` starts the bridge, and `setup` / `calibrate` / `bind`
are guided CLI wizards. See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for the
project layout.

## 📜 License

[MIT](LICENSE) — free to use, modify, and share. Made for the community. 💛
