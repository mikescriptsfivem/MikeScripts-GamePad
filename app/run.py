"""MikeScript Gamepad command-line entry point.

    python run.py list                  list detected HOTAS / joystick devices
    python run.py monitor [--device N]  live axis/button viewer (no driver needed)
    python run.py run [--profile P] [--device N]   start the bridge
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bridge import input as jin
from bridge.profile import Profile

DEFAULT_PROFILE = str(Path(__file__).resolve().parent.parent / "profiles" / "generic_flight.json")


def cmd_list() -> int:
    devices = jin.list_devices()
    if not devices:
        print("No devices found. Plug in your HOTAS and try again.")
        return 1
    for d in devices:
        print(
            f"[{d['index']}] {d['name']}  "
            f"(axes={d['axes']} buttons={d['buttons']} hats={d['hats']})"
        )
    return 0


def cmd_monitor(device: int) -> int:
    from bridge.monitor import monitor

    monitor(device)
    return 0


def cmd_run(profile_path: str, device: int | None) -> int:
    from bridge.engine import run

    try:
        profile = Profile.load(profile_path)
    except FileNotFoundError:
        print(f"Profile not found: {profile_path}")
        return 1
    try:
        run(profile, device_index=device)
    except RuntimeError as exc:
        print(f"\nError: {exc}")
        return 1
    return 0


def cmd_calibrate(profile_path: str, device: int | None) -> int:
    from bridge.calibrate import calibrate

    try:
        calibrate(profile_path, device)
    except FileNotFoundError:
        print(f"Profile not found: {profile_path}")
        return 1
    except RuntimeError as exc:
        print(f"\nError: {exc}")
        return 1
    return 0


def cmd_bind(profile_path: str, device: int | None) -> int:
    from bridge.bind import bind

    try:
        bind(profile_path, device)
    except FileNotFoundError:
        print(f"Profile not found: {profile_path}")
        return 1
    except RuntimeError as exc:
        print(f"\nError: {exc}")
        return 1
    return 0


def cmd_setup(profile_path: str, device: int | None) -> int:
    """Full guided setup: calibrate axes, then bind buttons."""
    rc = cmd_calibrate(profile_path, device)
    if rc != 0:
        return rc
    print("\n" + "=" * 60)
    print("Axes done. Now let's map your buttons.")
    print("=" * 60)
    return cmd_bind(profile_path, device)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mikescript-gamepad",
        description="Map any joystick / HOTAS to a virtual Xbox controller "
        "for FiveM / GTA V and other games.",
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="List detected joystick/HOTAS devices")

    p_mon = sub.add_parser("monitor", help="Live view of axes/buttons to find indices")
    p_mon.add_argument("--device", type=int, default=0)

    p_setup = sub.add_parser("setup", help="Guided setup: calibrate axes + bind buttons")
    p_setup.add_argument("--profile", default=DEFAULT_PROFILE)
    p_setup.add_argument("--device", type=int, default=None)

    p_cal = sub.add_parser("calibrate", help="Detect & map axes by moving each control")
    p_cal.add_argument("--profile", default=DEFAULT_PROFILE)
    p_cal.add_argument("--device", type=int, default=None)

    p_bind = sub.add_parser("bind", help="Map buttons by pressing them")
    p_bind.add_argument("--profile", default=DEFAULT_PROFILE)
    p_bind.add_argument("--device", type=int, default=None)

    p_run = sub.add_parser("run", help="Start the bridge")
    p_run.add_argument("--profile", default=DEFAULT_PROFILE)
    p_run.add_argument("--device", type=int, default=None)

    args = parser.parse_args(argv)

    if args.cmd == "list":
        return cmd_list()
    if args.cmd == "monitor":
        return cmd_monitor(args.device)
    if args.cmd == "setup":
        return cmd_setup(args.profile, args.device)
    if args.cmd == "calibrate":
        return cmd_calibrate(args.profile, args.device)
    if args.cmd == "bind":
        return cmd_bind(args.profile, args.device)
    if args.cmd == "run":
        return cmd_run(args.profile, args.device)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
