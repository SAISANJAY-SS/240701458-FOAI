"""OSRM road routing with validation and a safe demo fallback."""
from __future__ import annotations

from typing import Any

import httpx

OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
REQUEST_TIMEOUT_SECONDS = 8.0


def _validate_coordinate(latitude: float, longitude: float) -> None:
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Coordinates are outside valid latitude/longitude ranges")


def demo_fallback_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float, reason: str = "OSRM unavailable") -> dict[str, Any]:
    """Return a clearly labelled straight demo route when road routing is unavailable."""
    return {
        "success": False,
        "provider": "Demo Fallback",
        "algorithm": "Demo Fallback",
        "distance_m": 0,
        "distance_km": 0,
        "duration_s": 0,
        "eta_minutes": 0,
        "geometry": {"type": "LineString", "coordinates": [[start_lon, start_lat], [end_lon, end_lat]]},
        "steps": [],
        "alternatives": [],
        "error": reason,
    }


def _route_from_osrm(payload: dict[str, Any]) -> dict[str, Any]:
    routes = payload.get("routes")
    if payload.get("code") != "Ok" or not isinstance(routes, list) or not routes:
        raise ValueError(f"OSRM returned no route ({payload.get('code', 'unknown')})")

    def normalize_route(route: dict[str, Any]) -> dict[str, Any]:
        geometry = route.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") != "LineString" or not geometry.get("coordinates"):
            raise ValueError("OSRM returned an empty route geometry")
        return {
            "distance_m": round(float(route.get("distance", 0)), 1),
            "distance_km": round(float(route.get("distance", 0)) / 1000, 2),
            "duration_s": round(float(route.get("duration", 0))),
            "eta_minutes": max(1, round(float(route.get("duration", 0)) / 60)),
            "geometry": geometry,
            "steps": [step for leg in route.get("legs", []) for step in leg.get("steps", [])],
        }

    primary = normalize_route(routes[0])
    alternatives = [normalize_route(route) for route in routes[1:]]
    return {
        "success": True,
        "provider": "OSRM",
        "algorithm": "OSRM Road Routing",
        **primary,
        "alternatives": alternatives,
    }


async def get_real_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float, alternatives: bool = True) -> dict[str, Any]:
    """Request road geometry from the fixed public OSRM service."""
    try:
        _validate_coordinate(start_lat, start_lon)
        _validate_coordinate(end_lat, end_lon)
        params = {"overview": "full", "geometries": "geojson", "steps": "true", "alternatives": str(alternatives).lower()}
        url = f"{OSRM_URL}/{start_lon},{start_lat};{end_lon},{end_lat}"
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return _route_from_osrm(response.json())
    except (ValueError, httpx.HTTPError, TypeError, KeyError) as error:
        return demo_fallback_route(start_lat, start_lon, end_lat, end_lon, str(error))