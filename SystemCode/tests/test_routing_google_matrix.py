"""B-5: Google Routes travel matrix. Every test uses a fake transport; no paid API call is made."""

from datetime import datetime, timezone
import io
import json
import urllib.error

from fastapi.testclient import TestClient
import pytest

from roadguard.config import load_settings
from auth_test_support import create_app
from roadguard.routing import google_matrix
from roadguard.routing.google_matrix import GoogleRoutesMatrixProvider, TravelMatrixError, urllib_transport
from roadguard.routing.models import Depot
from roadguard.routing.planner import plan_routes
from roadguard.routing.settings import build_planning_input, default_crews, load_routing_config

from test_routing_api import create_task, recalculate, stops
from test_routing_core import PROJECT, snapshot


CONFIG = load_routing_config(environ={})
KEY_ENV = CONFIG.google_routes.api_key_env
SECRET = "test-key-not-real"
NOW = datetime(2026, 10, 15, 0, 0, tzinfo=timezone.utc)


class FakeGoogle:
    """Answers computeRouteMatrix like Google: proto3 JSON omits zero indexes and OK status.

    Durations are deliberately asymmetric (i->j != j->i) so index mix-ups are visible.
    """

    def __init__(self, unreachable=frozenset(), mutate=None):
        self.calls = []
        self.unreachable = unreachable
        self.mutate = mutate

    def seconds(self, origin, destination):
        return 60.0 * (10 * origin[0] + destination[0]) + 30.0 * origin[1] + destination[1]

    def __call__(self, url, headers, body, timeout):
        request = json.loads(body)
        self.calls.append({"url": url, "headers": dict(headers), "body": request, "timeout": timeout})
        coords = lambda w: (w["waypoint"]["location"]["latLng"]["latitude"],  # noqa: E731
                            w["waypoint"]["location"]["latLng"]["longitude"])
        origins = [coords(w) for w in request["origins"]]
        destinations = [coords(w) for w in request["destinations"]]
        elements = []
        for o, origin in enumerate(origins):
            for d, destination in enumerate(destinations):
                element = {"condition": "ROUTE_EXISTS"}
                if (origin, destination) in self.unreachable:
                    element = {"condition": "ROUTE_NOT_FOUND"}
                elif origin == destination:
                    element["duration"] = "0s"
                else:
                    element["duration"] = f"{self.seconds(origin, destination):g}s"
                if o:
                    element["originIndex"] = o
                if d:
                    element["destinationIndex"] = d
                elements.append(element)
        elements.reverse()  # Google streams elements in no guaranteed order.
        if self.mutate:
            elements = self.mutate(elements)
        return json.dumps(elements).encode()


DEPOT = (1.0, 2.0)
POINTS = [(3.0, 4.0), (5.0, 6.0), (7.0, 8.0)]


def planning_input(points=POINTS, start="2026-10-15T01:00:00Z"):
    """Fixture tasks with coordinates replaced so the fake can derive durations from them."""
    base = snapshot("tasks_20.json")
    tasks = [base.tasks[i % len(base.tasks)].model_copy(update={
        "task_id": f"task-{i}", "latitude": lat, "longitude": lon}) for i, (lat, lon) in enumerate(points)]
    return build_planning_input(
        base.model_copy(update={"tasks": tasks, "total": len(tasks)}), default_crews(PROJECT),
        Depot(depot_id="depot-nus-iss", latitude=DEPOT[0], longitude=DEPOT[1]), CONFIG.settings, start)


def provider(fake, **overrides):
    parameters = CONFIG.google_routes.model_copy(update=overrides)
    return GoogleRoutesMatrixProvider(parameters, transport=fake, environ={KEY_ENV: SECRET})


def expected_minutes(fake, a, b):
    return 0.0 if a == b else round(fake.seconds(a, b) / 60.0, 1)


@pytest.fixture(autouse=True)
def reject_real_network(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("tests must not call the real Google API")
    monkeypatch.setattr(google_matrix.urllib.request, "urlopen", fail)


def test_matrix_maps_indexes_keeps_asymmetry_and_unreachable_as_null():
    fake = FakeGoogle(unreachable={(POINTS[0], POINTS[1])})
    matrix = provider(fake).build(planning_input(), now=NOW)
    nodes = [DEPOT, *POINTS]
    assert matrix.node_ids == ["depot-nus-iss", "task-0", "task-1", "task-2"]
    assert matrix.is_simulated is False and matrix.provider == "google_routes_compute_route_matrix_v2"
    assert matrix.duration_minutes[1][2] is None  # ROUTE_NOT_FOUND is unreachable, never 0
    for i, a in enumerate(nodes):
        for j, b in enumerate(nodes):
            if (i, j) != (1, 2):
                assert matrix.duration_minutes[i][j] == expected_minutes(fake, a, b)
    assert matrix.duration_minutes[0][1] != matrix.duration_minutes[1][0]
    assert matrix.generated_at == NOW and matrix.parameters["billed_elements_per_fetch"] == 16
    assert SECRET not in json.dumps(matrix.model_dump(mode="json"))
    call = fake.calls[0]
    assert len(fake.calls) == 1 and call["url"] == CONFIG.google_routes.endpoint
    assert call["headers"]["X-Goog-Api-Key"] == SECRET
    assert call["headers"]["X-Goog-FieldMask"] == "originIndex,destinationIndex,duration,condition,status"
    assert call["body"]["travelMode"] == "DRIVE" and call["body"]["routingPreference"] == "TRAFFIC_UNAWARE"
    assert "departureTime" not in call["body"]


def test_large_inputs_are_split_into_blocks_within_the_element_cap():
    fake = FakeGoogle()
    matrix = provider(fake, max_elements_per_request=6).build(planning_input(), now=NOW)
    # 4 nodes: 4 destination columns, 1 origin row per request -> 4 requests of 4 elements.
    assert len(fake.calls) == 4 and matrix.parameters["request_count"] == 4
    assert all(len(c["body"]["origins"]) * len(c["body"]["destinations"]) <= 6 for c in fake.calls)
    nodes = [DEPOT, *POINTS]
    assert matrix.duration_minutes == [[expected_minutes(fake, a, b) for b in nodes] for a in nodes]


def test_many_nodes_respect_25_by_25_blocks():
    points = [(1.30 + i * 0.001, 103.70) for i in range(29)]
    fake = FakeGoogle()
    matrix = provider(fake).build(planning_input(points), now=NOW)
    assert all(len(c["body"]["origins"]) <= 25 and len(c["body"]["destinations"]) <= 25 for c in fake.calls)
    assert len(matrix.node_ids) == 30 and all(matrix.duration_minutes[i][i] == 0 for i in range(30))
    optimal = FakeGoogle()
    provider(optimal, routing_preference="TRAFFIC_AWARE_OPTIMAL").build(planning_input(points), now=NOW)
    assert all(len(c["body"]["origins"]) * len(c["body"]["destinations"]) <= 100 for c in optimal.calls)


def test_missing_key_and_node_cap_fail_before_any_request():
    fake = FakeGoogle()
    with pytest.raises(TravelMatrixError) as error:
        GoogleRoutesMatrixProvider(CONFIG.google_routes, transport=fake, environ={KEY_ENV: "  "}).build(
            planning_input(), now=NOW)
    assert error.value.reason == "missing_api_key"
    with pytest.raises(TravelMatrixError) as error:
        provider(fake, max_nodes=3).build(planning_input(), now=NOW)
    assert error.value.reason == "too_many_nodes" and fake.calls == []


@pytest.mark.parametrize("mutate, reason", [
    (lambda e: e[1:], "invalid_response"),                                    # missing element
    (lambda e: e + e[:1], "invalid_response"),                                # duplicate element
    (lambda e: [{**e[0], "originIndex": 9}, *e[1:]], "invalid_response"),    # index out of range
    (lambda e: [{**e[0], "duration": "12 minutes"}, *e[1:]], "invalid_response"),
    (lambda e: [{**e[0], "condition": "ROUTE_MATRIX_ELEMENT_CONDITION_UNSPECIFIED"}, *e[1:]],
     "invalid_response"),
    (lambda e: [{**e[0], "status": {"code": 3, "message": "bad"}}, *e[1:]], "element_error"),
    (lambda e: {"error": "not a list"}, "invalid_response"),
])
def test_malformed_or_partial_responses_are_errors_not_guesses(mutate, reason):
    with pytest.raises(TravelMatrixError) as error:
        provider(FakeGoogle(mutate=mutate)).build(planning_input(), now=NOW)
    assert error.value.reason == reason


def test_non_json_body_is_invalid_response():
    with pytest.raises(TravelMatrixError) as error:
        provider(lambda *args: b"<html>").build(planning_input(), now=NOW)
    assert error.value.reason == "invalid_response"


def test_traffic_unaware_matrices_are_cached_per_coordinates():
    fake = FakeGoogle()
    google = provider(fake)
    first = google.build(planning_input(), now=NOW)
    later = datetime(2026, 10, 15, 2, 0, tzinfo=timezone.utc)
    second = google.build(planning_input(), now=later)
    assert len(fake.calls) == 1 and second.parameters["served_from_cache"] is True
    assert second.duration_minutes == first.duration_minutes and second.generated_at == NOW
    google.build(planning_input(POINTS[:2]), now=later)
    assert len(fake.calls) == 2
    provider(fake, cache_entries=0).build(planning_input(), now=NOW)
    assert len(fake.calls) == 3


def test_traffic_aware_sends_only_future_departure_and_is_not_cached():
    fake = FakeGoogle()
    google = provider(fake, routing_preference="TRAFFIC_AWARE")
    future = google.build(planning_input(start="2026-10-15T01:00:00Z"), now=NOW)
    assert fake.calls[0]["body"]["departureTime"] == "2026-10-15T01:00:00Z"
    assert future.parameters["departure_time"] == "2026-10-15T01:00:00+00:00"
    past = google.build(planning_input(start="2026-10-14T01:00:00Z"), now=NOW)
    assert "departureTime" not in fake.calls[1]["body"] and past.parameters["departure_time"] is None
    google.build(planning_input(start="2026-10-14T01:00:00Z"), now=NOW)
    assert len(fake.calls) == 3


def test_urllib_transport_maps_errors_without_leaking_the_key(monkeypatch):
    def http_error(request, timeout):
        assert request.get_header("X-goog-api-key") == SECRET and timeout == 5
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, io.BytesIO(b"denied"))
    monkeypatch.setattr(google_matrix.urllib.request, "urlopen", http_error)
    with pytest.raises(TravelMatrixError) as error:
        urllib_transport("https://example.invalid", {"X-Goog-Api-Key": SECRET}, b"{}", 5)
    assert (error.value.reason, error.value.http_status) == ("http_error", 403)
    assert SECRET not in str(error.value)

    def timeout(request, timeout):
        raise urllib.error.URLError(TimeoutError())
    monkeypatch.setattr(google_matrix.urllib.request, "urlopen", timeout)
    with pytest.raises(TravelMatrixError) as error:
        urllib_transport("https://example.invalid", {}, b"{}", 5)
    assert error.value.reason == "timeout"

    def offline(request, timeout):
        raise urllib.error.URLError("no route")
    monkeypatch.setattr(google_matrix.urllib.request, "urlopen", offline)
    with pytest.raises(TravelMatrixError) as error:
        urllib_transport("https://example.invalid", {}, b"{}", 5)
    assert error.value.reason == "network_error"


def test_google_unreachable_tasks_get_reasons_in_both_planners():
    pi = planning_input()
    fake = FakeGoogle(unreachable={(DEPOT, POINTS[2])})
    matrix = provider(fake).build(pi, now=NOW)
    plans = [plan_routes(pi, matrix, "greedy")[0],
             plan_routes(pi, matrix, "ga", ga_parameters=CONFIG.ga, random_seed=1)[0]]
    for plan in plans:
        assert plan.matrix_is_simulated is False and plan.matrix_provider == matrix.provider
        assert [(u.task_id, u.reason) for u in plan.unassigned_tasks] == [("task-2", "unreachable_from_depot")]


def test_provider_override_is_validated():
    assert load_routing_config(environ={"ROADGUARD_TRAVEL_MATRIX_PROVIDER": "google_routes"}
                               ).travel_matrix_provider == "google_routes"
    with pytest.raises(ValueError):
        load_routing_config(environ={"ROADGUARD_TRAVEL_MATRIX_PROVIDER": "google"})


@pytest.fixture
def google_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ROADGUARD_TRAVEL_MATRIX_PROVIDER", "google_routes")
    settings = load_settings({"ROADGUARD_DB_PATH": str(tmp_path / "google.sqlite3")})
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client


def use_fake(client, fake, environ=None):
    service = client.app.state.planning_service
    assert service.config.travel_matrix_provider == "google_routes"
    service.google_matrix = GoogleRoutesMatrixProvider(
        service.config.google_routes, transport=fake, environ={KEY_ENV: SECRET} if environ is None else environ)


def test_recalculate_uses_google_matrix_for_both_algorithms(google_client):
    fake = FakeGoogle()
    use_fake(google_client, fake)
    tasks = [create_task(google_client, i) for i in range(3)]
    response = recalculate(google_client, 3)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["matrix_is_simulated"] is False and body["matrix_provider"] == "google_routes_compute_route_matrix_v2"
    assert body["matrix_generated_at"].endswith("Z") or body["matrix_generated_at"].endswith("+00:00")
    assert len(fake.calls) == 1  # Greedy and GA share one matrix
    for summary in body["plans"]:
        plan = google_client.get(f"/api/v1/route-plans/{summary['plan_id']}").json()
        assert plan["matrix_is_simulated"] is False and sorted(stops(plan)) == sorted(tasks)


@pytest.mark.parametrize("environ, transport, reason, status", [
    ({}, FakeGoogle(), "missing_api_key", None),
    (None, FakeGoogle(mutate=lambda e: e[1:]), "invalid_response", None),
    (None, "http403", "http_error", 403),
])
def test_google_failure_saves_nothing_and_never_falls_back(google_client, environ, transport, reason, status):
    if transport == "http403":
        def transport(*args):
            raise TravelMatrixError("http_error", 403)
    use_fake(google_client, transport, environ)
    create_task(google_client, 0)
    response = recalculate(google_client, 1)
    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "travel_matrix_unavailable" and body["details"]["reason"] == reason
    assert body["details"].get("http_status") == status and SECRET not in response.text
    for algorithm in ("ga", "greedy"):
        assert google_client.get(f"/api/v1/route-plans/latest?algorithm={algorithm}").status_code == 404


def test_total_travel_does_not_depend_on_crew_order():
    """Smoke-test legs: plain sum() gave 129.10000000000002 for one crew order and 129.1 for another."""
    from roadguard.routing.evaluation import RoutingProblem
    pi = planning_input()
    matrix = provider(FakeGoogle()).build(pi, now=NOW)
    rows = [row[:] for row in matrix.duration_minutes]
    for task, (out, back) in enumerate([(20.9, 18.8), (23.4, 23.9), (20.3, 21.8)], start=1):
        rows[0][task], rows[task][0] = out, back
    problem = RoutingProblem(pi, matrix.model_copy(update={"duration_minutes": rows}))
    totals = {problem.evaluate(routes).total_travel
              for routes in ([[2], [0], [1], []], [[1], [], [0], [2]], [[0], [1], [2], []], [[], [2], [1], [0]])}
    assert totals == {129.1}
