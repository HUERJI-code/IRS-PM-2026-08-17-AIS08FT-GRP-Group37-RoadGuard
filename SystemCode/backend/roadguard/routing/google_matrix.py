"""Google Routes API travel matrix (B-5): computeRouteMatrix -> TravelMatrix in minutes.

Rules this provider keeps (see routing/README.md section 10):
- Row i, column j is travel from node_ids[i] to node_ids[j]; Google's origin/destination
  indexes are mapped back explicitly, the matrix is never assumed symmetric.
- ROUTE_NOT_FOUND becomes null (unreachable), never zero minutes.
- Any other failure (missing key, HTTP/network error, element error, malformed or
  incomplete response) raises TravelMatrixError. The caller must not silently fall back
  to the simulated matrix: a failed Google request is reported, not disguised.
- The API key is read from the environment at call time and never logged, stored in
  the matrix parameters or returned in an error.
"""

from collections import OrderedDict
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import json
import os
import re
import socket
import threading
from typing import Literal
import urllib.error
import urllib.request

from .matrix import node_ids
from .models import PlanningInput, TravelMatrix
from .settings import GoogleRoutesParameters


# Google's documented per-request cap for computeRouteMatrix is 625 elements
# (100 for TRAFFIC_AWARE_OPTIMAL); blocks also stay within 25 origins x 25 destinations.
MAX_BLOCK_SIDE = 25
OPTIMAL_MAX_ELEMENTS = 100
FIELD_MASK = "originIndex,destinationIndex,duration,condition,status"
_DURATION = re.compile(r"^(\d+(?:\.\d+)?)s$")

TravelMatrixFailure = Literal[
    "missing_api_key", "too_many_nodes", "http_error", "timeout", "network_error",
    "invalid_response", "element_error",
]


class TravelMatrixError(Exception):
    """A matrix could not be produced. Messages are constant and contain no key or input."""

    def __init__(self, reason: TravelMatrixFailure, http_status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.http_status = http_status


# (url, headers, body, timeout_seconds) -> response body bytes; raises TravelMatrixError.
Transport = Callable[[str, Mapping[str, str], bytes, float], bytes]


def urllib_transport(url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> bytes:
    request = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise TravelMatrixError("http_error", exc.code) from None
    except (TimeoutError, socket.timeout):
        raise TravelMatrixError("timeout") from None
    except (urllib.error.URLError, OSError) as exc:
        if isinstance(getattr(exc, "reason", None), (TimeoutError, socket.timeout)):
            raise TravelMatrixError("timeout") from None
        raise TravelMatrixError("network_error") from None


def _waypoint(latitude: float, longitude: float) -> dict:
    return {"waypoint": {"location": {"latLng": {"latitude": latitude, "longitude": longitude}}}}


def _seconds(value: object) -> float:
    match = _DURATION.match(value) if isinstance(value, str) else None
    if match is None:
        raise TravelMatrixError("invalid_response")
    return float(match.group(1))


def _blocks(size: int, parameters: GoogleRoutesParameters) -> list[tuple[range, range]]:
    cap = parameters.max_elements_per_request
    if parameters.routing_preference == "TRAFFIC_AWARE_OPTIMAL":
        cap = min(cap, OPTIMAL_MAX_ELEMENTS)
    columns = min(size, MAX_BLOCK_SIDE, cap)
    rows = max(1, min(MAX_BLOCK_SIDE, cap // columns))
    return [(range(r, min(r + rows, size)), range(c, min(c + columns, size)))
            for r in range(0, size, rows) for c in range(0, size, columns)]


class GoogleRoutesMatrixProvider:
    """Builds one TravelMatrix per planning input; GA and Greedy share the result."""

    def __init__(self, parameters: GoogleRoutesParameters, *, transport: Transport | None = None,
                 environ: Mapping[str, str] | None = None) -> None:
        self.parameters = parameters
        self.transport = transport or urllib_transport
        self.environ = os.environ if environ is None else environ
        self._cache: OrderedDict[tuple, tuple[list[list[float | None]], datetime, int]] = OrderedDict()
        self._lock = threading.Lock()

    def _departure_time(self, planning_input: PlanningInput, now: datetime) -> datetime | None:
        # Traffic-unaware matrices are time independent. Google rejects past departure
        # times for driving, so a past planning start falls back to "request time"; the
        # departure actually used is recorded in the matrix parameters.
        if self.parameters.routing_preference == "TRAFFIC_UNAWARE":
            return None
        return planning_input.planning_start_at if planning_input.planning_start_at > now else None

    def _request_block(self, points, origins: range, destinations: range, api_key: str,
                       departure: datetime | None) -> dict[tuple[int, int], float | None]:
        body = {
            "origins": [_waypoint(*points[i]) for i in origins],
            "destinations": [_waypoint(*points[j]) for j in destinations],
            "travelMode": self.parameters.travel_mode,
            "routingPreference": self.parameters.routing_preference,
        }
        if departure is not None:
            body["departureTime"] = departure.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        headers = {"Content-Type": "application/json", "X-Goog-Api-Key": api_key,
                   "X-Goog-FieldMask": FIELD_MASK}
        raw = self.transport(self.parameters.endpoint, headers, json.dumps(body).encode("utf-8"),
                             self.parameters.timeout_seconds)
        try:
            elements = json.loads(raw)
        except (UnicodeError, ValueError):
            raise TravelMatrixError("invalid_response") from None
        if not isinstance(elements, list):
            raise TravelMatrixError("invalid_response")
        results: dict[tuple[int, int], float | None] = {}
        for element in elements:
            if not isinstance(element, dict):
                raise TravelMatrixError("invalid_response")
            # proto3 JSON omits zero values, so index 0 and an OK status may be absent.
            o, d = element.get("originIndex", 0), element.get("destinationIndex", 0)
            if (type(o) is not int or type(d) is not int or not 0 <= o < len(origins)
                    or not 0 <= d < len(destinations)):
                raise TravelMatrixError("invalid_response")
            key = (origins[o], destinations[d])
            if key in results:
                raise TravelMatrixError("invalid_response")
            status = element.get("status") or {}
            if not isinstance(status, dict) or status.get("code", 0) != 0:
                raise TravelMatrixError("element_error")
            condition = element.get("condition")
            if condition == "ROUTE_NOT_FOUND":
                results[key] = None
            elif condition == "ROUTE_EXISTS":
                results[key] = _seconds(element.get("duration"))
            else:
                raise TravelMatrixError("invalid_response")
        if len(results) != len(origins) * len(destinations):
            raise TravelMatrixError("invalid_response")
        return results

    def _fetch(self, points, api_key: str, departure: datetime | None) -> tuple[list[list[float | None]], int]:
        size = len(points)
        seconds: dict[tuple[int, int], float | None] = {}
        blocks = _blocks(size, self.parameters)
        for origins, destinations in blocks:
            seconds.update(self._request_block(points, origins, destinations, api_key, departure))
        digits = self.parameters.minutes_decimals
        durations = [
            [0.0 if i == j else (None if seconds[(i, j)] is None else round(seconds[(i, j)] / 60.0, digits))
             for j in range(size)]
            for i in range(size)
        ]
        return durations, len(blocks)

    def build(self, planning_input: PlanningInput, now: datetime | None = None) -> TravelMatrix:
        now = now or datetime.now(timezone.utc)
        points = [(planning_input.depot.latitude, planning_input.depot.longitude),
                  *((task.latitude, task.longitude) for task in planning_input.tasks)]
        if len(points) > self.parameters.max_nodes:
            raise TravelMatrixError("too_many_nodes")
        api_key = (self.environ.get(self.parameters.api_key_env) or "").strip()
        if not api_key:
            raise TravelMatrixError("missing_api_key")
        departure = self._departure_time(planning_input, now)
        cacheable = departure is None and self.parameters.routing_preference == "TRAFFIC_UNAWARE"
        key = (self.parameters.model_dump_json(), tuple(points))
        cached = None
        if cacheable and self.parameters.cache_entries:
            with self._lock:
                cached = self._cache.get(key)
                if cached is not None:
                    self._cache.move_to_end(key)
        if cached is None:
            durations, request_count = self._fetch(points, api_key, departure)
            fetched_at = now
            if cacheable and self.parameters.cache_entries:
                with self._lock:
                    self._cache[key] = (durations, fetched_at, request_count)
                    while len(self._cache) > self.parameters.cache_entries:
                        self._cache.popitem(last=False)
        else:
            durations, fetched_at, request_count = cached
        parameters = self.parameters.model_dump(mode="json", exclude={"api_key_env", "endpoint"})
        parameters.update({
            "departure_time": None if departure is None else departure.isoformat(),
            "request_count": request_count,
            "billed_elements_per_fetch": len(points) ** 2,
            "served_from_cache": cached is not None,
        })
        return TravelMatrix(
            node_ids=node_ids(planning_input),
            duration_minutes=[list(row) for row in durations],
            provider=self.parameters.provider,
            is_simulated=False,
            # When served from cache this is the original fetch time, not the reuse time.
            generated_at=fetched_at,
            parameters=parameters,
        )
