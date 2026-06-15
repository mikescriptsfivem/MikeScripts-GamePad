"""MikeScript Gamepad - graphical app.

One window that unifies everything:
  * pick your device
  * SEE every axis and button react live (so "is it registering?" is obvious)
  * map each control from a dropdown while watching it respond
  * Start/Stop the virtual Xbox controller

All HOTAS reading and virtual-pad output happen on a single background thread
(pygame and vgamepad are not thread-safe); the Tk UI only reads a snapshot.
"""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import pygame  # noqa: F401  (imported so a missing dep fails early & clearly)

from bridge.curves import clamp01
from bridge.library import (
    AUTORANGE_TARGETS,
    AXIS_OUTPUTS,
    BUTTON_OUTPUTS,
    build_profile,
    discover_profiles,
    identify_brand,
    selections_from_profile,
)
from bridge.mapper import compute_pad
from bridge.profile import Profile

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"
DEFAULT_PROFILE = PROFILES_DIR / "generic_flight.json"
NONE_LABEL = "— none —"


class Worker(threading.Thread):
    """Background loop: read HOTAS, optionally drive the virtual pad."""

    daemon = True

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._stop = False
        self.device_index = 0
        self._want_index = 0
        self.profile = Profile(name="empty")
        self.drive = False  # whether to push to the virtual pad
        # snapshot for the UI (read under lock)
        self.snap = {
            "ready": False, "error": "", "name": "", "n_axes": 0, "n_buttons": 0,
            "axes": [], "buttons": [], "hats": [], "out": None, "driving": False,
            "devices": [],
        }
        self._obs_min: list[float] = []
        self._obs_max: list[float] = []
        self._rest: list[float] = []
        self._rest_acc: list[float] = []
        self._rest_left: int = 0

    # ---- public, called from UI thread ----
    def set_device(self, idx: int) -> None:
        with self._lock:
            self._want_index = idx

    def set_profile(self, profile: Profile) -> None:
        with self._lock:
            self.profile = profile

    def set_drive(self, on: bool) -> None:
        with self._lock:
            self.drive = on

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self.snap)

    def stop(self) -> None:
        self._stop = True

    # ---- worker thread ----
    def run(self) -> None:
        import pygame as pg

        from bridge.output import VirtualPad

        pg.init()
        pg.joystick.init()
        js = None
        opened_index = -1
        pad = None
        loop_count = 0

        def open_device(i):
            nonlocal js, opened_index, self
            try:
                if pg.joystick.get_count() == 0:
                    return None
                i = max(0, min(i, pg.joystick.get_count() - 1))
                j = pg.joystick.Joystick(i)
                j.init()
                opened_index = i
                n = j.get_numaxes()
                self._obs_min = [1.0] * n
                self._obs_max = [-1.0] * n
                self._rest = [0.0] * n          # until measured, subtract nothing
                self._rest_acc = [0.0] * n
                self._rest_left = 20            # average first ~20 frames as rest
                return j
            except pg.error:
                return None

        while not self._stop:
            loop_count += 1
            with self._lock:
                want = self._want_index
                profile = self.profile
                drive = self.drive

            # publish the list of connected devices a few times a second
            if loop_count % 30 == 1:
                devs = []
                try:
                    for k in range(pg.joystick.get_count()):
                        jj = pg.joystick.Joystick(k)
                        jj.init()
                        devs.append({"index": k, "name": jj.get_name()})
                except pg.error:
                    pass
                with self._lock:
                    self.snap["devices"] = devs

            # (re)open device if needed
            if js is None or want != opened_index:
                pg.joystick.quit()
                pg.joystick.init()
                js = open_device(want)
                if js is None:
                    with self._lock:
                        self.snap.update(ready=False, error="No HOTAS detected — plug it in.",
                                         axes=[], buttons=[], hats=[], driving=False)
                    pg.time.wait(400)
                    continue
                self.device_index = opened_index

            pg.event.pump()
            axes = [js.get_axis(k) for k in range(js.get_numaxes())]
            buttons = [bool(js.get_button(k)) for k in range(js.get_numbuttons())]
            hats = [js.get_hat(k) for k in range(js.get_numhats())]

            # learn the resting position for the first few frames after opening,
            # so an off-centre axis (e.g. a combined-mode rudder) can't jam yaw on
            if self._rest_left > 0:
                for k in range(min(len(self._rest_acc), len(axes))):
                    self._rest_acc[k] += axes[k]
                self._rest_left -= 1
                if self._rest_left == 0:
                    self._rest = [a / 20.0 for a in self._rest_acc]

            # track observed range for trigger auto-calibration
            for k, v in enumerate(axes):
                if k < len(self._obs_min):
                    self._obs_min[k] = min(self._obs_min[k], v)
                    self._obs_max[k] = max(self._obs_max[k], v)

            # auto-range trigger/throttle axes so idle->full maps to 0..1.
            # The IDLE end is whichever extreme is closer to the resting position,
            # so a throttle that rests at -1 or at 0 both map idle->0, full->1
            # (this is what stops the throttle reading inverted).
            for am in profile.axes:
                if am.target in AUTORANGE_TARGETS and am.source < len(self._obs_min):
                    lo, hi = self._obs_min[am.source], self._obs_max[am.source]
                    if hi - lo > 0.3:
                        rest_v = self._rest[am.source] if am.source < len(self._rest) else 0.0
                        if abs(lo - rest_v) <= abs(hi - rest_v):
                            am.min, am.max = lo, hi   # idle is the low end
                        else:
                            am.min, am.max = hi, lo   # idle is the high end -> swap

            out = compute_pad(profile, [(axes, buttons, hats)], [self._rest])

            # zero any trigger/throttle whose axis hasn't shown enough travel yet
            for am in profile.axes:
                if am.target in AUTORANGE_TARGETS and am.source < len(self._obs_min):
                    if self._obs_max[am.source] - self._obs_min[am.source] <= 0.3:
                        if am.target in ("RT", "RT_LT_SPLIT"):
                            out.rt = 0.0
                        if am.target in ("LT", "RT_LT_SPLIT"):
                            out.lt = 0.0

            if drive:
                if pad is None:
                    try:
                        pad = VirtualPad()
                    except RuntimeError as exc:
                        with self._lock:
                            self.snap.update(error=str(exc))
                        drive = False
                if pad is not None:
                    pad.apply(out)
            elif pad is not None:
                pad.reset()

            with self._lock:
                self.snap.update(
                    ready=True, error="", name=js.get_name(),
                    n_axes=len(axes), n_buttons=len(buttons),
                    axes=axes, buttons=buttons, hats=hats,
                    out={"lx": out.lx, "ly": out.ly, "rx": out.rx, "ry": out.ry,
                         "lt": clamp01(out.lt), "rt": clamp01(out.rt),
                         "buttons": sorted(out.buttons),
                         "dpad": out.dpad},
                    driving=drive,
                )
            pg.time.wait(8)  # ~120 Hz

        if pad is not None:
            pad.reset()


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("MikeScript Gamepad")
        root.geometry("980x680")
        root.minsize(820, 560)

        self.worker = Worker()
        self.axis_vars: dict[str, tuple[tk.StringVar, tk.BooleanVar]] = {}
        self.button_vars: dict[str, tk.StringVar] = {}
        self.axis_bars: list[ttk.Progressbar] = []
        self.axis_val_labels: list[tk.Label] = []
        self.button_dots: list[tk.Label] = []
        self._built_axes = -1
        self._built_buttons = -1

        self._build_topbar()
        self._build_body()
        self._build_statusbar()

        self.worker.start()
        self._load_profiles_into_combo()
        if DEFAULT_PROFILE.exists():
            self._load_profile(str(DEFAULT_PROFILE))
        self._tick()

    # ---------- layout ----------
    def _build_topbar(self) -> None:
        bar = ttk.Frame(self.root, padding=8)
        bar.pack(fill="x")
        ttk.Label(bar, text="Device:").pack(side="left")
        self.device_combo = ttk.Combobox(bar, width=42, state="readonly")
        self.device_combo.pack(side="left", padx=6)
        self.device_combo.bind("<<ComboboxSelected>>", self._on_device_change)
        ttk.Button(bar, text="↻ Refresh", command=self._refresh_devices).pack(side="left")
        self.brand_label = ttk.Label(bar, text="", foreground="#06c")
        self.brand_label.pack(side="left", padx=8)

        ttk.Label(bar, text="    Profile:").pack(side="left")
        self.profile_combo = ttk.Combobox(bar, width=34, state="readonly")
        self.profile_combo.pack(side="left", padx=6)
        self.profile_combo.bind("<<ComboboxSelected>>", self._on_profile_pick)

    def _build_body(self) -> None:
        body = ttk.Frame(self.root, padding=(8, 0))
        body.pack(fill="both", expand=True)

        left = ttk.LabelFrame(body, text="LIVE INPUT  (move/press your HOTAS — it should react here)", padding=8)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.live_axes_frame = ttk.Frame(left)
        self.live_axes_frame.pack(fill="x")
        ttk.Separator(left).pack(fill="x", pady=6)
        ttk.Label(left, text="Buttons (light up when pressed):").pack(anchor="w")
        self.live_buttons_frame = ttk.Frame(left)
        self.live_buttons_frame.pack(fill="both", expand=True, pady=4)
        self.hat_label = ttk.Label(left, text="POV hat: —")
        self.hat_label.pack(anchor="w")

        right = ttk.LabelFrame(body, text="MAPPING  (pick which HOTAS control drives each output)", padding=8)
        right.pack(side="left", fill="both", expand=True)
        self._build_mapping(right)

    def _build_mapping(self, parent) -> None:
        canvas = tk.Canvas(parent, borderwidth=0, highlightthickness=0)
        scroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self._axis_combos = []
        ttk.Label(inner, text="AXES", font=("", 10, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 4))
        r = 1
        for target, label in AXIS_OUTPUTS:
            ttk.Label(inner, text=label, width=26).grid(row=r, column=0, sticky="w")
            src = tk.StringVar(value=NONE_LABEL)
            inv = tk.BooleanVar(value=False)
            cb = ttk.Combobox(inner, textvariable=src, width=10, state="readonly")
            cb.grid(row=r, column=1, padx=4, pady=1)
            cb.bind("<<ComboboxSelected>>", lambda e: self._push_profile())
            self._axis_combos.append(cb)
            chk = ttk.Checkbutton(inner, text="invert", variable=inv, command=self._push_profile)
            chk.grid(row=r, column=2, sticky="w")
            self.axis_vars[target] = (src, inv)
            r += 1

        # Rudder/yaw comes from an axis (twist) but drives the LB/RB *buttons*.
        ttk.Label(inner, text="Rudder / Yaw (twist axis → LB/RB)", width=26).grid(row=r, column=0, sticky="w")
        ysrc = tk.StringVar(value=NONE_LABEL)
        yinv = tk.BooleanVar(value=False)
        ycb = ttk.Combobox(inner, textvariable=ysrc, width=10, state="readonly")
        ycb.grid(row=r, column=1, padx=4, pady=1)
        ycb.bind("<<ComboboxSelected>>", lambda e: self._push_profile())
        self._axis_combos.append(ycb)
        ttk.Checkbutton(inner, text="invert", variable=yinv, command=self._push_profile).grid(row=r, column=2, sticky="w")
        self.rudder_var = (ysrc, yinv)
        r += 1

        ttk.Label(inner, text="BUTTONS", font=("", 10, "bold")).grid(row=r, column=0, sticky="w", pady=(10, 4))
        r += 1
        self._button_combos = []
        for target, label in BUTTON_OUTPUTS:
            ttk.Label(inner, text=label, width=26).grid(row=r, column=0, sticky="w")
            src = tk.StringVar(value=NONE_LABEL)
            cb = ttk.Combobox(inner, textvariable=src, width=10, state="readonly")
            cb.grid(row=r, column=1, padx=4, pady=1)
            cb.bind("<<ComboboxSelected>>", lambda e: self._push_profile())
            self._button_combos.append(cb)
            self.button_vars[target] = src
            r += 1

    def _build_statusbar(self) -> None:
        bar = ttk.Frame(self.root, padding=8)
        bar.pack(fill="x")
        self.start_btn = ttk.Button(bar, text="▶  Start Bridge", command=self._toggle_drive)
        self.start_btn.pack(side="left")
        ttk.Button(bar, text="✨ Auto-map", command=self._auto_map).pack(side="left", padx=6)
        ttk.Button(bar, text="💾 Save Profile", command=self._save_profile).pack(side="left")
        self.status = ttk.Label(bar, text="Starting…")
        self.status.pack(side="left", padx=10)
        self.out_label = ttk.Label(bar, text="", foreground="#0a7")
        self.out_label.pack(side="right")

    # ---------- device / profile ----------
    def _refresh_devices(self) -> None:
        self._dev_sig = None  # force _sync_devices to repopulate next tick

    def _sync_devices(self, snap) -> None:
        devs = snap.get("devices", [])
        sig = [(d["index"], d["name"]) for d in devs]
        if sig == getattr(self, "_dev_sig", "init"):
            return
        self._dev_sig = sig
        if not devs:
            self.device_combo["values"] = ["(no devices — plug in your HOTAS)"]
            self.device_combo.current(0)
            return
        values = [f"[{d['index']}] {d['name']}" for d in devs]
        self.device_combo["values"] = values
        if self.device_combo.get() not in values:
            self.device_combo.current(0)
            self.worker.set_device(devs[0]["index"])

    def _on_device_change(self, _evt=None) -> None:
        if self.device_combo.get().startswith("["):
            idx = int(self.device_combo.get().split("]")[0][1:])
            self.worker.set_device(idx)

    def _load_profiles_into_combo(self) -> None:
        self._profiles = discover_profiles(PROFILES_DIR)
        names = [p["name"] for p in self._profiles] or ["(no profiles)"]
        self.profile_combo["values"] = names
        if self._profiles:
            self.profile_combo.current(0)

    def _on_profile_pick(self, _evt=None) -> None:
        i = self.profile_combo.current()
        if 0 <= i < len(self._profiles):
            self._load_profile(self._profiles[i]["path"])

    def _load_profile(self, path: str) -> None:
        try:
            profile = Profile.load(path)
        except Exception as exc:
            messagebox.showerror("MikeScript Gamepad", f"Could not load profile:\n{exc}")
            return
        self._current_path = path
        axis_sel, button_sel, yaw = selections_from_profile(profile)
        for target, (src, inv) in axis_sel.items():
            if target in self.axis_vars:
                s, i = self.axis_vars[target]
                s.set(NONE_LABEL if src is None else str(src))
                i.set(inv)
        for target, src in button_sel.items():
            if target in self.button_vars:
                self.button_vars[target].set(NONE_LABEL if src is None else str(src))
        ysrc, yinv = yaw
        self.rudder_var[0].set(NONE_LABEL if ysrc is None else str(ysrc))
        self.rudder_var[1].set(yinv)
        self._device_hint = profile.device_name_contains or ""
        self._profile_name = profile.name
        self._push_profile()

    # ---------- mapping <-> worker ----------
    def _axis_options(self, n_axes: int) -> list[str]:
        return [NONE_LABEL] + [str(i) for i in range(n_axes)]

    def _button_options(self, n_buttons: int) -> list[str]:
        return [NONE_LABEL] + [str(i) for i in range(n_buttons)]

    def _refresh_combo_options(self, snap) -> None:
        if snap["n_axes"] != self._built_axes:
            opts = self._axis_options(snap["n_axes"])
            for cb in getattr(self, "_axis_combos", []):
                cb["values"] = opts
            self._built_axes = snap["n_axes"]
        if snap["n_buttons"] != self._built_buttons:
            opts = self._button_options(snap["n_buttons"])
            for cb in self._button_combos:
                cb["values"] = opts
            self._built_buttons = snap["n_buttons"]

    def _push_profile(self) -> None:
        axis_sel = {}
        for target, (s, inv) in self.axis_vars.items():
            val = s.get()
            axis_sel[target] = (None if val == NONE_LABEL else int(val), bool(inv.get()))
        button_sel = {}
        for target, s in self.button_vars.items():
            val = s.get()
            button_sel[target] = None if val == NONE_LABEL else int(val)
        ys, yi = self.rudder_var
        yaw_val = ys.get()
        yaw = (None if yaw_val == NONE_LABEL else int(yaw_val), bool(yi.get()))
        profile = build_profile(
            getattr(self, "_profile_name", "Custom"),
            getattr(self, "_device_hint", ""),
            axis_sel, button_sel, yaw,
        )
        self.worker.set_profile(profile)

    def _save_profile(self) -> None:
        self._push_profile()
        suggested = Path(getattr(self, "_current_path", str(DEFAULT_PROFILE))).name
        path = filedialog.asksaveasfilename(
            title="Save profile",
            initialdir=str(PROFILES_DIR),
            initialfile=suggested,
            defaultextension=".json",
            filetypes=[("MikeScript Gamepad profile", "*.json")],
        )
        if not path:
            return
        self.worker.profile.name = Path(path).stem.replace("_", " ")
        try:
            self.worker.profile.save(path)
            self._current_path = path
            self.status.config(text=f"Saved → {Path(path).name}")
            self._load_profiles_into_combo()
        except Exception as exc:
            messagebox.showerror("MikeScript Gamepad", f"Could not save:\n{exc}")

    def _auto_map(self) -> None:
        """Assign a sensible default mapping for whatever device is selected.

        Near-universal flight layout: axis 0/1 = roll/pitch, axis 2 = throttle
        (with reverse), a likely twist axis = yaw, first buttons = common actions.
        The live panel + dropdowns let the user fix anything that's off.
        """
        snap = self.worker.snapshot()
        na, nb = snap["n_axes"], snap["n_buttons"]
        if na == 0 and nb == 0:
            self.status.config(text="Auto-map: no device yet — pick one first.")
            return
        # clear everything
        for s, i in self.axis_vars.values():
            s.set(NONE_LABEL)
            i.set(False)
        for s in self.button_vars.values():
            s.set(NONE_LABEL)
        self.rudder_var[0].set(NONE_LABEL)
        self.rudder_var[1].set(False)

        def ax(target, src, inv=False):
            if src < na and target in self.axis_vars:
                self.axis_vars[target][0].set(str(src))
                self.axis_vars[target][1].set(inv)

        ax("LEFT_X", 0)
        ax("LEFT_Y", 1, inv=True)
        ax("RT", 2)                       # throttle = gas (safe; idle = no gas)
        # rudder twist: axis 5 on many HOTAS (e.g. Hotas One), else axis 3 if present
        if na > 5:
            self.rudder_var[0].set("5")
        elif na > 3:
            self.rudder_var[0].set("3")
        # buttons -> common actions; reserve the first one for Brake/reverse (LT)
        if nb > 0:
            self.button_vars["LT_FULL"].set("0")   # hold = brake / back up
        for idx, target in enumerate(["A", "B", "X", "Y", "START", "BACK", "LS"], start=1):
            if idx < nb:
                self.button_vars[target].set(str(idx))
        self._push_profile()
        self.status.config(
            text="Auto-mapped. Sweep throttle once, then ▶ Start. "
            "(Brake/back-up = hold the LT button; flip 'invert' if throttle feels reversed.)"
        )

    def _toggle_drive(self) -> None:
        new = not self.worker.drive
        self.worker.set_drive(new)
        self.start_btn.config(text="■  Stop Bridge" if new else "▶  Start Bridge")

    # ---------- live update ----------
    def _tick(self) -> None:
        snap = self.worker.snapshot()
        self._sync_devices(snap)
        self._refresh_combo_options(snap)
        self._update_live(snap)
        if snap["ready"] and snap["name"]:
            self.brand_label.config(text="✓ " + identify_brand(snap["name"]))
        else:
            self.brand_label.config(text="")
        if snap["error"]:
            self.status.config(text="⚠ " + snap["error"])
        elif snap["ready"]:
            self.status.config(text=("● BRIDGE LIVE — " if snap["driving"] else "Reading ") + snap["name"])
        self.root.after(33, self._tick)

    def _ensure_live_widgets(self, n_axes: int, n_buttons: int) -> None:
        if len(self.axis_bars) != n_axes:
            for w in self.live_axes_frame.winfo_children():
                w.destroy()
            self.axis_bars, self.axis_val_labels = [], []
            for i in range(n_axes):
                row = ttk.Frame(self.live_axes_frame)
                row.pack(fill="x", pady=1)
                ttk.Label(row, text=f"Axis {i}", width=7).pack(side="left")
                bar = ttk.Progressbar(row, length=220, maximum=2000)
                bar.pack(side="left", padx=4)
                lbl = ttk.Label(row, text="+0.00", width=7)
                lbl.pack(side="left")
                self.axis_bars.append(bar)
                self.axis_val_labels.append(lbl)
        if len(self.button_dots) != n_buttons:
            for w in self.live_buttons_frame.winfo_children():
                w.destroy()
            self.button_dots = []
            cols = 8
            for i in range(n_buttons):
                dot = tk.Label(self.live_buttons_frame, text=str(i), width=3, relief="ridge",
                               bg="#ddd", fg="#333")
                dot.grid(row=i // cols, column=i % cols, padx=2, pady=2)
                self.button_dots.append(dot)

    def _update_live(self, snap) -> None:
        self._ensure_live_widgets(snap["n_axes"], snap["n_buttons"])
        for i, v in enumerate(snap["axes"]):
            if i < len(self.axis_bars):
                self.axis_bars[i]["value"] = int((v + 1.0) * 1000)
                self.axis_val_labels[i].config(text=f"{v:+.2f}")
        for i, pressed in enumerate(snap["buttons"]):
            if i < len(self.button_dots):
                self.button_dots[i].config(bg="#2c8" if pressed else "#ddd",
                                           fg="white" if pressed else "#333")
        hats = snap["hats"]
        self.hat_label.config(text=f"POV hat: {hats[0] if hats else '—'}")
        out = snap.get("out")
        if out:
            pressed = " ".join(out["buttons"]) or "-"
            self.out_label.config(
                text=f"OUT  L({out['lx']:+.1f},{out['ly']:+.1f})  R({out['rx']:+.1f},{out['ry']:+.1f})"
                f"  LT{out['lt']:.1f} RT{out['rt']:.1f}  [{pressed}]"
            )


def main() -> None:
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.worker.stop(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
