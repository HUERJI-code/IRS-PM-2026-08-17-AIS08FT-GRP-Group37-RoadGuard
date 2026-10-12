"""Service-area union, boundary semantics and fail-closed geometry loading."""

import json
from pathlib import Path

import pytest

from roadguard.errors import AppError
from roadguard.geography import JurongScope


ROAD = "public_motor_road"


def square(low=0, high=10):
    return [[low, low], [high, low], [high, high], [low, high], [low, low]]


def configured(tmp_path, coordinates, geometry_type="Polygon"):
    path = tmp_path / "scope.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": geometry_type, "coordinates": coordinates}}
    ]}), encoding="utf-8")
    return JurongScope(path)


@pytest.fixture(scope="module")
def real_scope():
    return JurongScope()


def test_real_jurong_area_and_depot_exclusion(real_scope):
    assert real_scope.scope_version == "jurong-je-jw-mp2025-v1"
    real_scope.validate(1.3405, 103.706, ROAD)
    real_scope.validate(1.333, 103.742, ROAD)
    for latitude, longitude in ((1.292149, 103.776551), (0, 0), (1.363, 103.755)):
        with pytest.raises(AppError) as raised:
            real_scope.validate(latitude, longitude, ROAD)
        assert (raised.value.code, raised.value.status_code) == ("outside_service_area", 422)


def test_default_scope_is_independent_of_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    JurongScope().validate(1.3405, 103.706, ROAD)


def test_real_polygon_vertex_and_edge_midpoint_are_included(real_scope):
    path = Path(__file__).resolve().parents[2] / "Miscellaneous/geography/jurong-boundary-mp2025.geojson"
    points = json.loads(path.read_text(encoding="utf-8"))["features"][0]["geometry"]["coordinates"][0]
    first, second = points[:2]
    real_scope.validate(first[1], first[0], ROAD)
    real_scope.validate((first[1] + second[1]) / 2, (first[0] + second[0]) / 2, ROAD)


def test_hole_interiors_are_excluded_but_all_ring_edges_are_included(tmp_path):
    scope = configured(tmp_path, [square(), square(3, 7)])
    for latitude, longitude in ((1, 1), (0, 5), (10, 10), (5, 3), (3, 3)):
        scope.validate(latitude, longitude, ROAD)
    for latitude, longitude in ((5, 5), (-1, 5), (11, 5)):
        with pytest.raises(AppError, match="outside the service area"):
            scope.validate(latitude, longitude, ROAD)


def test_multipolygon_union_includes_each_component_and_excludes_gap(tmp_path):
    scope = configured(tmp_path, [[square(0, 4)], [square(10, 14)]], "MultiPolygon")
    scope.validate(2, 2, ROAD)
    scope.validate(12, 12, ROAD)
    scope.validate(10, 12, ROAD)
    with pytest.raises(AppError):
        scope.validate(7, 7, ROAD)


def test_feature_union_can_cover_a_hole_from_another_feature(tmp_path):
    scope = configured(tmp_path, [square(), square(3, 7)])
    path = tmp_path / "scope.geojson"
    source = json.loads(path.read_text())
    source["features"].append({"type": "Feature", "geometry": {
        "type": "Polygon", "coordinates": [square(4, 6)]
    }})
    path.write_text(json.dumps(source), encoding="utf-8")
    JurongScope(path).validate(5, 5, ROAD)
    with pytest.raises(AppError):
        scope.validate(5, 5, ROAD)


@pytest.mark.parametrize("latitude,longitude", [
    (True, 103.7), ("1.34", 103.7), (1.34, "103.7"), (91, 0), (-91, 0),
    (0, 181), (0, -181), (float("nan"), 0), (0, float("inf")), (None, 0),
])
def test_coordinates_require_finite_legal_json_numbers(real_scope, latitude, longitude):
    with pytest.raises(AppError) as raised:
        real_scope.validate(latitude, longitude, ROAD)
    assert (raised.value.code, raised.value.status_code) == ("validation_error", 422)


@pytest.mark.parametrize("road", ["expressway", "ramp", "private_road", "restricted", "", None])
def test_only_explicit_public_motor_road_declaration_is_accepted(real_scope, road):
    with pytest.raises(AppError) as raised:
        real_scope.validate(1.3405, 103.706, road)
    assert (raised.value.code, raised.value.status_code) == ("unsupported_road_type", 422)


@pytest.mark.parametrize("coordinates,geometry_type", [
    ([], "Polygon"), ([square()[:-1]], "Polygon"), ([[[0, 0], [1, 1], [2, 2], [0, 0]]], "Polygon"),
    ([[[0, 0], [4, 4], [0, 4], [4, 0], [0, 0]]], "Polygon"),
    ([[[0, 0], [5, 0], [1, 4], [4, 4], [0, 0]]], "Polygon"),
    ([square(), square(11, 12)], "Polygon"), ([], "MultiPolygon"),
    ([square()], "LineString"), ([[[False, 0], [4, 0], [4, 4], [False, 0]]], "Polygon"),
    ([[[0, 0], [181, 0], [4, 4], [0, 0]]], "Polygon"),
])
def test_malformed_geometry_is_rejected_eagerly(tmp_path, coordinates, geometry_type):
    with pytest.raises(AppError) as raised:
        configured(tmp_path, coordinates, geometry_type)
    assert (raised.value.code, raised.value.status_code) == ("service_area_unavailable", 503)
    assert str(tmp_path) not in raised.value.message


@pytest.mark.parametrize("content", ["not JSON", "null", "{}", '{"type":"FeatureCollection","features":[]}', '{"type":"x","type":"FeatureCollection","features":[]}'])
def test_invalid_scope_documents_fail_closed_with_safe_errors(tmp_path, content):
    path = tmp_path / "private-secret-scope.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(AppError) as raised:
        JurongScope(path)
    assert raised.value.code == "service_area_unavailable"
    assert "private-secret" not in raised.value.message


def test_missing_scope_file_fails_closed(tmp_path):
    with pytest.raises(AppError) as raised:
        JurongScope(tmp_path / "missing.json")
    assert raised.value.status_code == 503
