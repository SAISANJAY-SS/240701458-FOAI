from __future__ import annotations

import asyncio
import math
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .ai_engine import decide_sos, dynamic_replanning, route_with_blockage, team_allocation
from .services.routing_service import demo_fallback_route, get_real_route

app = FastAPI(title="ResQAI API", version="0.1.0", description="Explainable disaster response decision support demo")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


class DemoMemoryRepository:
    def __init__(self) -> None:
        self.sos_requests: dict[str, dict[str, Any]] = {}
        self.teams: dict[str, dict[str, Any]] = {
            "Team 01": {"id": "Team 01", "name": "Team 01", "status": "AVAILABLE", "members": 6, "skills": ["Flood Rescue"], "medical_capability": False, "vehicle": "Rescue Boat", "current_location": [12.9716, 77.5946], "ETA": 8, "assigned_sos": None, "availability": True},
            "Team 02": {"id": "Team 02", "name": "Team 02", "status": "AVAILABLE", "members": 5, "skills": ["Medical Rescue"], "medical_capability": True, "vehicle": "Ambulance", "current_location": [12.9740, 77.5915], "ETA": 10, "assigned_sos": None, "availability": True},
            "Team 03": {"id": "Team 03", "name": "Team 03", "status": "AVAILABLE", "members": 7, "skills": ["Urban Rescue"], "medical_capability": False, "vehicle": "Rescue Van", "current_location": [12.9732, 77.5968], "ETA": 12, "assigned_sos": None, "availability": True},
            "Team 04": {"id": "Team 04", "name": "Team 04", "status": "AVAILABLE", "members": 6, "skills": ["Flood Rescue", "Medical Support"], "medical_capability": True, "vehicle": "Rescue Boat", "current_location": [12.9728, 77.5940], "ETA": 13, "assigned_sos": None, "availability": True},
            "Team 05": {"id": "Team 05", "name": "Team 05", "status": "AVAILABLE", "members": 5, "skills": ["Search & Rescue"], "medical_capability": False, "vehicle": "Rescue Van", "current_location": [12.9752, 77.5930], "ETA": 15, "assigned_sos": None, "availability": True},
        }
        self.shelters: dict[str, dict[str, Any]] = {
            "Shelter 01": {"id": "Shelter 01", "name": "Community Relief Center", "latitude": 12.9735, "longitude": 77.5985, "capacity": 500, "occupancy": 220, "available_capacity": 280, "medical_support": False, "accessibility": True, "status": "OPEN"},
            "Shelter 07": {"id": "Shelter 07", "name": "Central Relief Shelter", "latitude": 12.9838, "longitude": 77.5960, "capacity": 750, "occupancy": 320, "available_capacity": 430, "medical_support": True, "accessibility": True, "status": "OPEN"},
        }
        self.hospitals: dict[str, dict[str, Any]] = {
            "Hospital 01": {"id": "Hospital 01", "name": "City General Hospital", "latitude": 12.9860, "longitude": 77.6040, "emergency_capacity": 200, "available_beds": 34, "ambulance_support": True, "specialties": ["surgery", "trauma"], "status": "OPEN"},
        }
        self.resources: dict[str, dict[str, Any]] = {
            "Ambulance 02": {"id": "Ambulance 02", "type": "ambulance", "status": "AVAILABLE", "location": [12.9724, 77.5938]},
            "Medical Kit 03": {"id": "Medical Kit 03", "type": "medical_kit", "status": "AVAILABLE", "location": [12.9728, 77.5940]},
        }
        self.road_conditions: dict[str, str] = {"junction_b": "SAFE", "junction_c": "SAFE", "junction_d": "SAFE"}
        self.connections: set[WebSocket] = set()
        self.tracking_tasks: dict[str, asyncio.Task[Any]] = {}
        self.demo_role = "OFFICER"

    def create_sos(self, payload: dict[str, Any], role: str) -> dict[str, Any]:
        decision = decide_sos(payload)
        sos_id = f"SOS-{uuid4().hex[:8].upper()}"
        record = {
            "id": sos_id,
            "status": "PRIORITIZED",
            "severity": payload.get("severity", "high"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "citizen_role": role,
            "emergency_type": payload.get("emergency_type", "Flood"),
            "description": payload.get("description", "Citizen emergency report"),
            "latitude": float(payload.get("latitude", 12.9716)),
            "longitude": float(payload.get("longitude", 77.5946)),
            "people_affected": int(payload.get("people_affected", 1)),
            "medical_assistance": bool(payload.get("medical_assistance", False)),
            "flood_level": payload.get("flood_level", "high"),
            "rainfall": payload.get("rainfall", "high"),
            "river_proximity": payload.get("river_proximity", "high"),
            "flood_reports": int(payload.get("flood_reports", 0)),
            "priority": decision["priority"],
            "assigned_team": decision["recommended_team"],
            "recommended_shelter": decision["recommended_shelter"],
            "recommended_hospital": decision["recommended_hospital"],
            "ai_decision": decision,
            "route_status": "AI ANALYSIS",
            "timeline": [],
            "tracking": {"progress": 0.0, "distance_travelled_m": 0.0, "distance_remaining_m": 0.0, "eta_minutes": 0, "current_road": None, "next_road": None, "simulated": True},
        }
        self.sos_requests[sos_id] = record
        team = self.teams.get(decision["recommended_team"])
        if team:
            team["assigned_sos"] = sos_id
            team["status"] = "ASSIGNED"
            team["availability"] = False
            record["team_location"] = {"latitude": team["current_location"][0], "longitude": team["current_location"][1], "simulated": True}
        shelter = self.shelters.get(decision["recommended_shelter"])
        if shelter:
            record["shelter_location"] = {"latitude": shelter["latitude"], "longitude": shelter["longitude"]}
        return record

    def list_sos(self) -> list[dict[str, Any]]:
        return list(self.sos_requests.values())

    def get_sos(self, sos_id: str) -> dict[str, Any]:
        if sos_id not in self.sos_requests:
            raise HTTPException(status_code=404, detail="SOS not found")
        return self.sos_requests[sos_id]

    def patch_sos(self, sos_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        record = self.get_sos(sos_id)
        for key, value in updates.items():
            if value is not None:
                record[key] = value
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        if updates.get("status"):
            record["status"] = updates["status"]
        return record

    def attach_route(self, sos_id: str, route: dict[str, Any]) -> dict[str, Any]:
        record = self.get_sos(sos_id)
        record["route"] = route
        record["route_status"] = "ROUTE CALCULATED" if route.get("success") else "DEMO FALLBACK"
        record["tracking"] = {**record["tracking"], "distance_remaining_m": route.get("distance_m", 0), "eta_minutes": route.get("eta_minutes", 0)}
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        return record

    def add_timeline(self, sos_id: str, label: str, simulated: bool = False) -> dict[str, Any]:
        record = self.get_sos(sos_id)
        item = {"timestamp": datetime.now(timezone.utc).isoformat(), "label": label, "simulated": simulated}
        record.setdefault("timeline", []).append(item)
        record["updated_at"] = item["timestamp"]
        return item

    def dashboard_data(self) -> dict[str, Any]:
        active_sos = [item for item in self.sos_requests.values() if item["status"] not in {"RESOLVED", "CANCELLED"}]
        critical_count = sum(1 for item in active_sos if item.get("priority") == "CRITICAL")
        teams = list(self.teams.values())
        available_teams = sum(1 for team in teams if team["status"] == "AVAILABLE")
        available_ambulances = sum(1 for resource in self.resources.values() if resource["type"] == "ambulance" and resource["status"] == "AVAILABLE")
        return {
            "active_sos": len(active_sos),
            "critical_count": critical_count,
            "available_teams": available_teams,
            "available_ambulances": available_ambulances,
            "recent_sos": sorted(active_sos, key=lambda x: x["created_at"], reverse=True)[:5],
            "active_teams": [team for team in teams if team["status"] != "OFFLINE"],
            "shelters": list(self.shelters.values()),
            "hospitals": list(self.hospitals.values()),
            "ai_statistics": {"avg_risk": round(sum(item["ai_decision"]["risk"]["unsafe_probability"] for item in active_sos) / max(len(active_sos), 1), 2), "critical_incidents": critical_count, "route_algorithm": "Weighted A*"},
        }

    def get_teams(self) -> list[dict[str, Any]]:
        return list(self.teams.values())

    def get_team(self, team_id: str) -> dict[str, Any]:
        team = self.teams.get(team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        return team

    def patch_team(self, team_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        team = self.get_team(team_id)
        for key, value in updates.items():
            if value is not None:
                team[key] = value
        return team

    def assign_team(self, team_id: str, sos_id: str) -> dict[str, Any]:
        team = self.get_team(team_id)
        team["assigned_sos"] = sos_id
        team["status"] = "ASSIGNED"
        team["availability"] = False
        return team

    def set_team_status(self, team_id: str, status: str) -> dict[str, Any]:
        team = self.get_team(team_id)
        team["status"] = status
        team["availability"] = status == "AVAILABLE"
        return team

    def get_shelters(self) -> list[dict[str, Any]]: return list(self.shelters.values())
    def get_shelter(self, shelter_id: str) -> dict[str, Any]:
        shelter = self.shelters.get(shelter_id)
        if not shelter: raise HTTPException(status_code=404, detail="Shelter not found")
        return shelter

    def get_hospitals(self) -> list[dict[str, Any]]: return list(self.hospitals.values())
    def get_hospital(self, hospital_id: str) -> dict[str, Any]:
        hospital = self.hospitals.get(hospital_id)
        if not hospital: raise HTTPException(status_code=404, detail="Hospital not found")
        return hospital


repo = DemoMemoryRepository()
connections: set[WebSocket] = repo.connections


class SOSRequest(BaseModel):
    emergency_type: str = "Flood"
    severity: str = "high"
    description: str = ""
    latitude: float = Field(12.9716, ge=-90, le=90)
    longitude: float = Field(77.5946, ge=-180, le=180)
    people_affected: int = Field(1, ge=1, le=1000)
    medical_assistance: bool = False
    flood_level: str = "high"
    rainfall: str = "high"
    river_proximity: str = "high"
    flood_reports: int = Field(3, ge=0, le=100)


class TeamAssignmentRequest(BaseModel):
    sos_id: str


class TeamStatusRequest(BaseModel):
    status: str = "AVAILABLE"


class SOSUpdateRequest(BaseModel):
    status: str | None = None
    priority: str | None = None
    assigned_team: str | None = None
    recommended_shelter: str | None = None
    recommended_hospital: str | None = None


def current_user(x_demo_role: str | None = Header(default=None, alias="X-Demo-Role")) -> str:
    return x_demo_role or repo.demo_role


async def broadcast_event(event: str, payload: dict[str, Any], sos_id: str | None = None) -> None:
    event_sos_id = sos_id or payload.get("sos_id")
    message = {"event": event, "type": event.upper(), "timestamp": datetime.now(timezone.utc).isoformat(), "sos_id": event_sos_id, "data": payload}
    for websocket in list(connections):
        try:
            await websocket.send_json(message)
        except Exception:
            connections.discard(websocket)


def _distance_m(first: list[float], second: list[float]) -> float:
    lat1, lon1 = math.radians(first[1]), math.radians(first[0])
    lat2, lon2 = math.radians(second[1]), math.radians(second[0])
    delta_lat, delta_lon = lat2 - lat1, lon2 - lon1
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return 6371000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _route_progress(route: dict[str, Any], progress: float) -> dict[str, Any]:
    coordinates = route.get("geometry", {}).get("coordinates", [])
    if not coordinates:
        return {"latitude": 0.0, "longitude": 0.0, "distance_travelled_m": 0.0, "distance_remaining_m": 0.0, "current_road": None, "next_road": None}
    lengths = [_distance_m(coordinates[index - 1], coordinates[index]) for index in range(1, len(coordinates))]
    total = sum(lengths) or float(route.get("distance_m", 0))
    target = total * progress
    travelled = 0.0
    point = coordinates[-1]
    segment_index = len(lengths) - 1
    for index, segment_length in enumerate(lengths):
        if travelled + segment_length >= target:
            ratio = (target - travelled) / segment_length if segment_length else 0.0
            point = [coordinates[index][0] + (coordinates[index + 1][0] - coordinates[index][0]) * ratio, coordinates[index][1] + (coordinates[index + 1][1] - coordinates[index][1]) * ratio]
            segment_index = index
            break
        travelled += segment_length
    steps = [step for step in route.get("steps", []) if step.get("name")]
    step_names = [str(step["name"]) for step in steps]
    current_road = step_names[min(segment_index, len(step_names) - 1)] if step_names else None
    next_road = step_names[min(segment_index + 1, len(step_names) - 1)] if step_names else None
    return {"latitude": point[1], "longitude": point[0], "distance_travelled_m": round(total * progress, 1), "distance_remaining_m": round(total * (1 - progress), 1), "current_road": current_road, "next_road": next_road}


async def _track_sos(sos_id: str) -> None:
    record = repo.get_sos(sos_id)
    route = record.get("route", {})
    if not route.get("geometry", {}).get("coordinates"):
        record["route_status"] = "ROUTE UNAVAILABLE"
        return
    record["status"] = "TEAM EN ROUTE"
    record["route_status"] = "TEAM EN ROUTE"
    repo.add_timeline(sos_id, "Team departed", simulated=True)
    await broadcast_event("team_departed", {"sos_id": sos_id, "team_id": record["assigned_team"]}, sos_id)
    await broadcast_event("route_status", {"sos_id": sos_id, "status": "TEAM EN ROUTE"}, sos_id)
    try:
        for tick in range(1, 21):
            progress = tick / 20
            tracking = _route_progress(route, progress)
            tracking.update({"progress": progress, "eta_minutes": max(0, round(route.get("duration_s", 0) * (1 - progress) / 60)), "simulated": True})
            record["tracking"] = tracking
            record["team_location"] = {"latitude": tracking["latitude"], "longitude": tracking["longitude"], "simulated": True}
            await broadcast_event("team_position_updated", {"sos_id": sos_id, "team_id": record["assigned_team"], **tracking}, sos_id)
            if tick < 20:
                await asyncio.sleep(0.75)
        record["status"] = "ARRIVED"
        record["route_status"] = "ARRIVED"
        repo.add_timeline(sos_id, "Team arrived at destination", simulated=True)
        await broadcast_event("team_arrived", {"sos_id": sos_id, "team_id": record["assigned_team"]}, sos_id)
    except asyncio.CancelledError:
        raise
    finally:
        repo.tracking_tasks.pop(sos_id, None)


async def start_tracking_for_sos(sos_id: str) -> dict[str, Any]:
    record = repo.get_sos(sos_id)
    existing = repo.tracking_tasks.get(sos_id)
    if existing and not existing.done():
        return record
    repo.add_timeline(sos_id, "Tracking started", simulated=True)
    repo.tracking_tasks[sos_id] = asyncio.create_task(_track_sos(sos_id))
    return record


@app.get("/health")
def health() -> dict[str, Any]:
    return {"success": True, "data": {"service": "resqai-api", "demo_mode": True}, "message": "ok"}


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    return {"success": True, "data": {**repo.dashboard_data(), "sos": repo.list_sos()}, "message": "Demo command center data"}


@app.get("/api/sos")
def list_all_sos() -> dict[str, Any]:
    return {"success": True, "data": repo.list_sos(), "message": "SOS list"}


@app.post("/api/sos")
async def create_sos(request: SOSRequest, role: str = Depends(current_user)) -> dict[str, Any]:
    record = repo.create_sos(request.model_dump(), role)
    shelter = repo.shelters[record["recommended_shelter"]]
    route = await get_real_route(record["latitude"], record["longitude"], shelter["latitude"], shelter["longitude"])
    record = repo.attach_route(record["id"], route)
    repo.add_timeline(record["id"], "SOS received", simulated=False)
    repo.add_timeline(record["id"], "AI analysis completed", simulated=False)
    repo.add_timeline(record["id"], f"{record['assigned_team']} assigned", simulated=False)
    repo.add_timeline(record["id"], "OSRM route calculated", simulated=False)
    record["ai_decision"]["explanation"].append(
        "OSRM generated real road geometry from the citizen location to the recommended shelter."
        if route["provider"] == "OSRM"
        else "OSRM was unavailable; the route is explicitly labelled Demo Fallback."
    )
    await broadcast_event("sos_created", record, record["id"])
    await broadcast_event("ai_analysis_completed", {"sos_id": record["id"], "priority": record["priority"]}, record["id"])
    await broadcast_event("team_assigned", {"sos_id": record["id"], "team_id": record["assigned_team"]}, record["id"])
    await broadcast_event("route_calculated", {"sos_id": record["id"], "route": route}, record["id"])
    await broadcast_event("dashboard_update", repo.dashboard_data())
    return {"success": True, "data": record, "message": "SOS received and prioritized in demo mode."}


@app.get("/api/sos/{sos_id}")
def get_sos(sos_id: str) -> dict[str, Any]:
    record = repo.get_sos(sos_id)
    return {"success": True, "data": record, "message": "SOS details"}


@app.get("/api/sos/{sos_id}/tracking")
def get_tracking(sos_id: str) -> dict[str, Any]:
    record = repo.get_sos(sos_id)
    return {"success": True, "data": {"sos_id": sos_id, "status": record["status"], "route_status": record.get("route_status"), "tracking": record.get("tracking"), "timeline": record.get("timeline", [])}, "message": "Tracking state"}


@app.post("/api/sos/{sos_id}/start")
async def start_tracking(sos_id: str) -> dict[str, Any]:
    record = await start_tracking_for_sos(sos_id)
    return {"success": True, "data": record, "message": "Simulated team tracking started"}


@app.post("/api/sos/{sos_id}/complete")
async def complete_sos(sos_id: str) -> dict[str, Any]:
    record = repo.get_sos(sos_id)
    task = repo.tracking_tasks.pop(sos_id, None)
    if task and not task.done():
        task.cancel()
    record["status"] = "RESOLVED"
    record["route_status"] = "RESCUE COMPLETED"
    repo.add_timeline(sos_id, "Rescue completed", simulated=True)
    team = repo.teams.get(record["assigned_team"])
    if team:
        team["status"] = "AVAILABLE"
        team["assigned_sos"] = None
        team["availability"] = True
    await broadcast_event("rescue_completed", {"sos_id": sos_id, "team_id": record["assigned_team"], "status": "RESOLVED"}, sos_id)
    await broadcast_event("dashboard_update", repo.dashboard_data())
    return {"success": True, "data": record, "message": "Rescue completed"}


@app.patch("/api/sos/{sos_id}")
async def update_sos(sos_id: str, updates: SOSUpdateRequest) -> dict[str, Any]:
    payload = {k: v for k, v in updates.model_dump().items() if v is not None}
    record = repo.patch_sos(sos_id, payload)
    await broadcast_event("sos_updated", record)
    await broadcast_event("dashboard_update", repo.dashboard_data())
    return {"success": True, "data": record, "message": "SOS updated"}


@app.delete("/api/sos/{sos_id}")
async def delete_sos(sos_id: str) -> dict[str, Any]:
    if sos_id not in repo.sos_requests:
        raise HTTPException(status_code=404, detail="SOS not found")
    del repo.sos_requests[sos_id]
    await broadcast_event("dashboard_update", repo.dashboard_data())
    return {"success": True, "message": "SOS deleted"}


@app.get("/api/teams")
def list_teams() -> dict[str, Any]:
    return {"success": True, "data": repo.get_teams(), "message": "Teams"}


@app.get("/api/teams/{team_id}")
def get_team(team_id: str) -> dict[str, Any]:
    return {"success": True, "data": repo.get_team(team_id), "message": "Team"}


@app.patch("/api/teams/{team_id}")
async def patch_team(team_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    team = repo.patch_team(team_id, updates)
    await broadcast_event("team_status_changed", team)
    await broadcast_event("dashboard_update", repo.dashboard_data())
    return {"success": True, "data": team, "message": "Team updated"}


@app.post("/api/teams/{team_id}/assign")
async def assign_team(team_id: str, payload: TeamAssignmentRequest) -> dict[str, Any]:
    team = repo.assign_team(team_id, payload.sos_id)
    await broadcast_event("team_assigned", {"team_id": team_id, "sos_id": payload.sos_id, "team": team})
    await broadcast_event("dashboard_update", repo.dashboard_data())
    return {"success": True, "data": team, "message": "Team assigned"}


@app.post("/api/teams/{team_id}/status")
async def set_team_status(team_id: str, payload: TeamStatusRequest) -> dict[str, Any]:
    team = repo.set_team_status(team_id, payload.status)
    await broadcast_event("team_status_changed", team)
    await broadcast_event("dashboard_update", repo.dashboard_data())
    return {"success": True, "data": team, "message": "Status updated"}


@app.get("/api/shelters")
def list_shelters() -> dict[str, Any]:
    return {"success": True, "data": repo.get_shelters(), "message": "Shelters"}


@app.get("/api/shelters/{shelter_id}")
def get_shelter(shelter_id: str) -> dict[str, Any]:
    return {"success": True, "data": repo.get_shelter(shelter_id), "message": "Shelter"}


@app.get("/api/hospitals")
def list_hospitals() -> dict[str, Any]:
    return {"success": True, "data": repo.get_hospitals(), "message": "Hospitals"}


@app.get("/api/hospitals/{hospital_id}")
def get_hospital(hospital_id: str) -> dict[str, Any]:
    return {"success": True, "data": repo.get_hospital(hospital_id), "message": "Hospital"}


@app.get("/api/ai/decision/{sos_id}")
def ai_decision(sos_id: str) -> dict[str, Any]:
    record = repo.get_sos(sos_id)
    if "ai_decision" not in record:
        raise HTTPException(status_code=404, detail="AI decision not found")
    return {"success": True, "data": record["ai_decision"], "message": "AI decision"}


@app.get("/api/routing/route")
async def routing_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float, alternatives: bool = True) -> dict[str, Any]:
    route = await get_real_route(start_lat, start_lon, end_lat, end_lon, alternatives)
    return {"success": route["success"], "data": route, "message": "Road route calculated"}


@app.post("/api/simulation/flood-sos")
async def create_demo_flood() -> dict[str, Any]:
    payload = {
        "emergency_type": "Flood",
        "severity": "critical",
        "description": "Citizen trapped in a flood near the river corridor.",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "people_affected": 3,
        "medical_assistance": True,
        "flood_level": "high",
        "rainfall": "high",
        "river_proximity": "high",
        "flood_reports": 3,
    }
    record = repo.create_sos(payload, "OFFICER")
    shelter = repo.shelters[record["recommended_shelter"]]
    route = await get_real_route(record["latitude"], record["longitude"], shelter["latitude"], shelter["longitude"])
    record = repo.attach_route(record["id"], route)
    repo.add_timeline(record["id"], "SOS received", simulated=False)
    repo.add_timeline(record["id"], "AI analysis completed", simulated=False)
    repo.add_timeline(record["id"], f"{record['assigned_team']} assigned", simulated=False)
    repo.add_timeline(record["id"], "OSRM route calculated", simulated=False)
    record["ai_decision"]["explanation"].append(
        "OSRM generated real road geometry from the citizen location to the recommended shelter."
        if route["provider"] == "OSRM"
        else "OSRM was unavailable; the route is explicitly labelled Demo Fallback."
    )
    await broadcast_event("sos_created", record, record["id"])
    await broadcast_event("ai_analysis_completed", {"sos_id": record["id"], "priority": record["priority"]}, record["id"])
    await broadcast_event("team_assigned", {"sos_id": record["id"], "team_id": record["assigned_team"]}, record["id"])
    await broadcast_event("route_calculated", {"sos_id": record["id"], "route": route}, record["id"])
    await broadcast_event("dashboard_update", repo.dashboard_data())
    return {"success": True, "data": record, "message": "Demo flood SOS created"}


@app.post("/api/simulation/road-block")
async def simulate_road_block() -> dict[str, Any]:
    repo.road_conditions["junction_b"] = "BLOCKED"
    blocked_route = dynamic_replanning(["citizen", "junction_a", "junction_b", "shelter_07"], "citizen", "shelter_07", repo.road_conditions)
    latest = max(repo.sos_requests.values(), key=lambda item: item["created_at"], default=None)
    if latest:
        task = repo.tracking_tasks.pop(latest["id"], None)
        if task and not task.done():
            task.cancel()
        latest["status"] = "ROAD BLOCKED"
        latest["route_status"] = "ROAD BLOCKED"
        repo.add_timeline(latest["id"], "Road blockage detected", simulated=True)
    await broadcast_event("road_blocked", {"junction": "junction_b", "status": "BLOCKED", "replan": blocked_route, "sos_id": latest["id"] if latest else None})
    await broadcast_event("route_replanning", {"sos_id": latest["id"] if latest else None, "reason": "Simulated flooding reported on junction_b"})
    if latest:
        shelter = repo.shelters[latest["recommended_shelter"]]
        route = await get_real_route(latest["latitude"], latest["longitude"], shelter["latitude"], shelter["longitude"])
        latest = repo.attach_route(latest["id"], route)
        latest["status"] = "TEAM EN ROUTE"
        latest["route_status"] = "ALTERNATIVE ROUTE"
        repo.add_timeline(latest["id"], "Alternative route selected", simulated=True)
        await broadcast_event("route_updated", {"sos_id": latest["id"], "route": route, "ai_replan": blocked_route}, latest["id"])
    await broadcast_event("dashboard_update", repo.dashboard_data())
    return {"success": True, "data": {"road_conditions": repo.road_conditions, "replan": blocked_route, "route": latest.get("route") if latest else demo_fallback_route(0, 0, 0, 0, "No active SOS")}, "message": "Road blockage simulated and replan produced"}


@app.post("/api/simulation/replan")
async def simulate_replan() -> dict[str, Any]:
    route = dynamic_replanning(["citizen", "junction_a", "junction_b", "shelter_07"], "citizen", "shelter_07", repo.road_conditions)
    await broadcast_event("route_updated", route)
    await broadcast_event("dashboard_update", repo.dashboard_data())
    return {"success": True, "data": route, "message": "Replanning completed"}


@app.post("/api/simulation/rescue-complete")
async def complete_rescue() -> dict[str, Any]:
    for record in repo.sos_requests.values():
        task = repo.tracking_tasks.pop(record["id"], None)
        if task and not task.done():
            task.cancel()
        record["status"] = "RESOLVED"
        record["route_status"] = "RESCUE COMPLETED"
        repo.add_timeline(record["id"], "Rescue completed", simulated=True)
        await broadcast_event("rescue_completed", {"sos_id": record["id"], "status": "RESOLVED"}, record["id"])
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
    for team in repo.teams.values():
        team["status"] = "AVAILABLE"
        team["assigned_sos"] = None
        team["availability"] = True
    await broadcast_event("dashboard_update", repo.dashboard_data())
    return {"success": True, "message": "Rescue completed and resources reset"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    connections.add(websocket)
    await websocket.send_json({"event": "connected", "data": {"status": "connected", "active_sos": len(repo.sos_requests)}})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connections.discard(websocket)


@app.websocket("/ws/officer/{officer_id}")
async def officer_socket(websocket: WebSocket, officer_id: str) -> None:
    await websocket.accept()
    connections.add(websocket)
    await websocket.send_json({"event": "connected", "data": {"officer_id": officer_id, "active_sos": len(repo.sos_requests)}})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connections.discard(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
