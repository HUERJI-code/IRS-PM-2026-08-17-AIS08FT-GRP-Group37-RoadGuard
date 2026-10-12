"""Frozen service-area containment; road eligibility is a caller declaration."""

import json
import math
from pathlib import Path

from roadguard.errors import AppError


_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_SCOPE = _ROOT / "Miscellaneous/geography/jurong-boundary-mp2025.geojson"


def _number(value, low, high):
    return type(value) in (int, float) and low <= value <= high and math.isfinite(value)


def _ring_position(point, ring):
    """Return -1 outside, 0 on an edge, 1 inside; winding direction is irrelevant."""
    x, y = point
    inside = False
    for (ax, ay), (bx, by) in zip(ring, ring[1:]):
        dx, dy = bx - ax, by - ay
        cross = dx * (y - ay) - dy * (x - ax)
        tolerance = 1e-12 * math.hypot(dx, dy)
        if abs(cross) <= tolerance and (
            min(ax, bx) - 1e-12 <= x <= max(ax, bx) + 1e-12
            and min(ay, by) - 1e-12 <= y <= max(ay, by) + 1e-12
        ):
            return 0
        if (ay > y) != (by > y) and x < ax + (y - ay) * dx / dy:
            inside = not inside
    return 1 if inside else -1


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _intersects(a, b, c, d):
    if (
        max(a[0], b[0]) < min(c[0], d[0]) or max(c[0], d[0]) < min(a[0], b[0])
        or max(a[1], b[1]) < min(c[1], d[1]) or max(c[1], d[1]) < min(a[1], b[1])
    ):
        return False
    return _cross(a, b, c) * _cross(a, b, d) <= 0 and _cross(c, d, a) * _cross(c, d, b) <= 0


def _parse_ring(source):
    if not isinstance(source, list) or len(source) < 4:
        raise ValueError
    ring = []
    for point in source:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError
        longitude, latitude = point
        if not _number(longitude, -180, 180) or not _number(latitude, -90, 90):
            raise ValueError
        ring.append((longitude, latitude))
    if ring[0] != ring[-1] or len(set(ring[:-1])) != len(ring) - 1:
        raise ValueError
    origin = ring[0]
    if sum(_cross(origin, a, b) for a, b in zip(ring, ring[1:])) == 0:
        raise ValueError
    segments = list(zip(ring, ring[1:]))
    for i, (a, b) in enumerate(segments):
        for j in range(i + 2, len(segments)):
            if i == 0 and j == len(segments) - 1:
                continue
            if _intersects(a, b, *segments[j]):
                raise ValueError
    return tuple(ring)


def _parse_polygon(source):
    if not isinstance(source, list) or not source:
        raise ValueError
    rings = tuple(_parse_ring(ring) for ring in source)
    for index, hole in enumerate(rings[1:], start=1):
        if any(_ring_position(point, rings[0]) != 1 for point in hole[:-1]):
            raise ValueError
        for other in rings[:index]:
            if any(_intersects(a, b, c, d) for a, b in zip(hole, hole[1:]) for c, d in zip(other, other[1:])):
                raise ValueError
        if any(_ring_position(hole[0], other) == 1 or _ring_position(other[0], hole) == 1 for other in rings[1:index]):
            raise ValueError
    return rings


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


class JurongScope:
    scope_version = "jurong-je-jw-mp2025-v1"

    def __init__(self, path: Path | None = None):
        source_path = _DEFAULT_SCOPE if path is None else Path(path)
        if not source_path.is_absolute():
            source_path = _ROOT / source_path
        try:
            source = json.loads(source_path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
            if source["type"] != "FeatureCollection" or not isinstance(source["features"], list) or not source["features"]:
                raise ValueError
            polygons = []
            for feature in source["features"]:
                if feature["type"] != "Feature":
                    raise ValueError
                geometry = feature["geometry"]
                if geometry["type"] == "Polygon":
                    polygons.append(_parse_polygon(geometry["coordinates"]))
                elif geometry["type"] == "MultiPolygon" and geometry["coordinates"]:
                    polygons.extend(_parse_polygon(item) for item in geometry["coordinates"])
                else:
                    raise ValueError
            self._polygons = tuple(polygons)
        except (OSError, UnicodeError, ValueError, KeyError, TypeError, OverflowError):
            raise AppError("service_area_unavailable", "The service area configuration is unavailable.", 503) from None

    def validate(self, latitude, longitude, road_type) -> None:
        if not _number(latitude, -90, 90) or not _number(longitude, -180, 180):
            raise AppError("validation_error", "Coordinates must be finite WGS84 numbers.", 422)
        if road_type != "public_motor_road":
            raise AppError("unsupported_road_type", "Only declared public motor road tasks are supported.", 422)
        point = (longitude, latitude)
        for polygon in self._polygons:
            outer = _ring_position(point, polygon[0])
            if outer == 0:
                return
            if outer == 1 and all(_ring_position(point, hole) != 1 for hole in polygon[1:]):
                return
        raise AppError("outside_service_area", "The task location is outside the service area.", 422)
