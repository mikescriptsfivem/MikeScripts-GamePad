"""The single source of truth for turning raw HOTAS input into a PadState.

Both the command-line bridge (engine.py) and the GUI use this, so the mapping
behaves identically everywhere.

Input is ``frames``: a list indexed by device slot, each item ``(axes, buttons,
hats)`` for that physical controller. ``rest`` is the matching list of resting
axis values per device (or None). Single-device profiles just use slot 0.
"""

from __future__ import annotations

from .curves import axis_value
from .output import PadState

_EMPTY = ([], [], [])


def _frame(frames, device: int):
    if frames and 0 <= device < len(frames) and frames[device] is not None:
        return frames[device]
    return _EMPTY


def _rest_for(rest, device: int):
    if rest and 0 <= device < len(rest):
        return rest[device]
    return None


def _accumulate_axis(st: PadState, target: str, v: float) -> None:
    if target == "LEFT_X":
        st.lx = v
    elif target == "LEFT_Y":
        st.ly = v
    elif target == "RIGHT_X":
        st.rx = v
    elif target == "RIGHT_Y":
        st.ry = v
    elif target == "LT":
        st.lt = (v + 1.0) / 2.0  # full-range axis (-1..1) -> trigger (0..1)
    elif target == "RT":
        st.rt = (v + 1.0) / 2.0
    elif target == "RT_LT_SPLIT":
        # one lever -> both triggers: centre = neutral, push = RT (gas),
        # pull = LT (brake/reverse). Deadzone (in axis_value) holds neutral.
        if v >= 0.0:
            st.rt = v
        else:
            st.lt = -v


def _apply_button_target(st: PadState, target: str) -> None:
    if target == "RT_FULL":
        st.rt = 1.0
    elif target == "LT_FULL":
        st.lt = 1.0
    else:
        st.buttons.add(target)


def compute_pad(profile, frames, rest=None) -> PadState:
    """Map the current per-device raw input to a virtual-pad state."""
    st = PadState()

    for am in profile.axes:
        axes, _, _ = _frame(frames, getattr(am, "device", 0))
        if am.source < len(axes):
            _accumulate_axis(st, am.target, axis_value(axes[am.source], am))

    for ab in profile.axis_buttons:
        dev = getattr(ab, "device", 0)
        axes, _, _ = _frame(frames, dev)
        if ab.source < len(axes):
            v = axes[ab.source]
            r = _rest_for(rest, dev)
            if r and ab.source < len(r):
                v -= r[ab.source]  # treat resting position as zero
            if ab.invert:
                v = -v
            if ab.negative and v <= -ab.threshold:
                st.buttons.add(ab.negative)
            elif ab.positive and v >= ab.threshold:
                st.buttons.add(ab.positive)

    for bm in profile.buttons:
        _, buttons, _ = _frame(frames, getattr(bm, "device", 0))
        if bm.source < len(buttons) and buttons[bm.source]:
            _apply_button_target(st, bm.target)

    for hm in profile.hats:
        _, _, hats = _frame(frames, getattr(hm, "device", 0))
        if hm.source < len(hats):
            hx, hy = hats[hm.source]
            st.dpad = (st.dpad[0] or hx, st.dpad[1] or hy)

    return st
