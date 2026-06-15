"""Profile model: how each physical HOTAS input maps to the virtual pad.

A profile is plain JSON so you can edit it by hand. See ``profiles/`` for
examples and the README for a field-by-field explanation.

Multi-device: every mapping has a ``device`` *slot* (default 0). A profile's
``devices`` list names the physical controller behind each slot, so a setup
split across a separate stick / throttle / rudder pedals (even mixed brands)
all feeds one virtual pad.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

# Valid analog targets on the virtual Xbox pad.
AXIS_TARGETS = {"LEFT_X", "LEFT_Y", "RIGHT_X", "RIGHT_Y", "LT", "RT", "RT_LT_SPLIT"}


def _only_known(cls, data: dict) -> dict:
    """Drop unknown keys (e.g. `comment`) so profiles can carry annotations."""
    allowed = {f.name for f in fields(cls)}
    return {k: v for k, v in data.items() if k in allowed}


@dataclass
class AxisMap:
    """A physical axis -> an analog stick axis or a trigger."""

    source: int            # axis index on its device (see live view / monitor)
    target: str            # one of AXIS_TARGETS
    device: int = 0        # which device slot this axis comes from
    invert: bool = False
    deadzone: float = 0.05
    expo: float = 0.0
    sensitivity: float = 1.0
    min: float = -1.0
    max: float = 1.0


@dataclass
class ButtonMap:
    """A physical button -> a pad button, or a fully-pressed trigger."""

    source: int  # button index on its device
    target: str  # A/B/X/Y/LB/RB/LS/RS/BACK/START/GUIDE/DPAD_* or LT_FULL/RT_FULL
    device: int = 0


@dataclass
class AxisButtonsMap:
    """An analog axis -> two digital buttons (e.g. rudder twist -> LB/RB yaw)."""

    source: int
    negative: str | None = None  # pressed when axis < -threshold
    positive: str | None = None  # pressed when axis > +threshold
    device: int = 0
    threshold: float = 0.5
    invert: bool = False


@dataclass
class HatMap:
    """A POV hat -> the D-pad."""

    source: int
    target: str = "DPAD"
    device: int = 0


@dataclass
class Profile:
    name: str
    device_index: int | None = None
    device_name_contains: str | None = None
    update_rate_hz: int = 120
    devices: list = field(default_factory=list)  # slot -> {"name_contains": ...}
    axes: list[AxisMap] = field(default_factory=list)
    buttons: list[ButtonMap] = field(default_factory=list)
    axis_buttons: list[AxisButtonsMap] = field(default_factory=list)
    hats: list[HatMap] = field(default_factory=list)

    @staticmethod
    def load(path: str | Path) -> "Profile":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return Profile(
            name=data.get("name", "Unnamed"),
            device_index=data.get("device_index"),
            device_name_contains=data.get("device_name_contains"),
            update_rate_hz=int(data.get("update_rate_hz", 120)),
            devices=data.get("devices", []),
            axes=[AxisMap(**_only_known(AxisMap, a)) for a in data.get("axes", [])],
            buttons=[ButtonMap(**_only_known(ButtonMap, b)) for b in data.get("buttons", [])],
            axis_buttons=[
                AxisButtonsMap(**_only_known(AxisButtonsMap, ab))
                for ab in data.get("axis_buttons", [])
            ],
            hats=[HatMap(**_only_known(HatMap, h)) for h in data.get("hats", [])],
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    def max_device_slot(self) -> int:
        """Highest device slot referenced by any mapping."""
        slots = [0]
        for group in (self.axes, self.buttons, self.axis_buttons, self.hats):
            slots += [getattr(m, "device", 0) for m in group]
        return max(slots)
