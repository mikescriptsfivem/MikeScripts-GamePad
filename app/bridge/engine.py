"""The main loop: read HOTAS device(s) -> PadState -> push to the virtual pad."""

from __future__ import annotations

import time
from typing import Callable

from .input import JoystickInput, find_device_by_name
from .mapper import compute_pad
from .output import VirtualPad
from .profile import Profile


def _capture_rest(src, frames: int = 20) -> list[float]:
    """Average a device's axes at startup to learn each one's resting position."""
    acc: list[float] = []
    for _ in range(frames):
        axes, _, _ = src.poll()
        if not acc:
            acc = list(axes)
        else:
            for i in range(min(len(acc), len(axes))):
                acc[i] += axes[i]
        time.sleep(1 / 240)
    return [a / frames for a in acc] if acc else []


def _resolve_devices(profile: Profile, device_index: int | None) -> list[int]:
    """Return a physical device index per profile slot."""
    if profile.devices:
        resolved = []
        for slot in profile.devices:
            hint = (slot or {}).get("name_contains") if isinstance(slot, dict) else None
            idx = find_device_by_name(hint) if hint else None
            resolved.append(idx if idx is not None else len(resolved))
        return resolved
    # single-device profile
    if device_index is not None:
        return [device_index]
    if profile.device_index is not None:
        return [profile.device_index]
    if profile.device_name_contains:
        found = find_device_by_name(profile.device_name_contains)
        if found is not None:
            return [found]
    return [0]


def run(
    profile: Profile,
    device_index: int | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> None:
    indices = _resolve_devices(profile, device_index)
    sources = [JoystickInput(i) for i in indices]
    pad = VirtualPad()

    print(f"[MikeScript Gamepad] Profile: {profile.name}")
    for slot, src in enumerate(sources):
        print(f"[MikeScript Gamepad] Device slot {slot}: {src.name}  "
              f"(axes={src.num_axes} buttons={src.num_buttons} hats={src.num_hats})")
    print("[MikeScript Gamepad] Leave all controls centred for a moment (calibrating rest)...")
    rest = [_capture_rest(src) for src in sources]
    print("[MikeScript Gamepad] Virtual Xbox 360 pad is live. Press Ctrl+C to stop.\n")

    period = 1.0 / max(1, profile.update_rate_hz)
    try:
        while True:
            if should_stop is not None and should_stop():
                break
            t0 = time.perf_counter()
            frames = [src.poll() for src in sources]
            pad.apply(compute_pad(profile, frames, rest))
            elapsed = time.perf_counter() - t0
            if elapsed < period:
                time.sleep(period - elapsed)
    except KeyboardInterrupt:
        pass
    finally:
        pad.reset()
        print("\n[MikeScript Gamepad] Stopped. Virtual pad reset to neutral.")
