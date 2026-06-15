"""Shaping a raw axis value into a usable analog output.

Order of operations: calibrate (min/max -> -1..1) -> invert -> deadzone ->
expo -> sensitivity -> clamp.
"""

from __future__ import annotations


def clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def clamp01(v: float) -> float:
    return clamp(v, 0.0, 1.0)


def _normalize(raw: float, lo: float, hi: float) -> float:
    """Map the calibrated range [lo, hi] onto [-1, 1]."""
    half = (hi - lo) / 2.0
    if half == 0:
        return 0.0
    center = (lo + hi) / 2.0
    return clamp((raw - center) / half)


def _deadzone(v: float, dz: float) -> float:
    """Zero out small movements, then rescale so motion still reaches 1.0."""
    if dz <= 0:
        return v
    if abs(v) <= dz:
        return 0.0
    sign = 1.0 if v > 0 else -1.0
    return sign * (abs(v) - dz) / (1.0 - dz)


def _expo(v: float, e: float) -> float:
    """Soften response near centre while keeping the endpoints at +/-1."""
    if e <= 0:
        return v
    e = clamp(e, 0.0, 1.0)
    return (1.0 - e) * v + e * (v ** 3)


def axis_value(raw: float, amap) -> float:
    """Apply a profile AxisMap to a raw pygame axis reading."""
    v = _normalize(raw, amap.min, amap.max)
    if amap.invert:
        v = -v
    v = _deadzone(v, amap.deadzone)
    v = _expo(v, amap.expo)
    v *= amap.sensitivity
    return clamp(v)
