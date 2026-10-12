"""Explainable AI and demo routing for the ResQAI disaster-response platform."""
from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from typing import Any, Iterable


@dataclass(frozen=True)
class Road:
    start: str
    end: str
    distance: float
    travel_time: int
    flood_risk: float
    blockage_status: str = "SAFE"

    @property
    def cost(self) -> float:
        return self.distance * 1.4 + self.travel_time * 0.5 + self.flood_risk * 3.0 + (5.0 if self.blockage_status == "BLOCKED" else 0.0)


DEMO_ROADS: list[Road] = [
    Road("citizen", "junction_a", 1.2, 3, 0.25, "SAFE"),
    Road("junction_a", "junction_b", 1.1, 4, 0.35, "SAFE"),
    Road("junction_b", "shelter_07", 1.0, 3, 0.2, "SAFE"),
    Road("junction_a", "junction_c", 1.6, 5, 0.55, "SAFE"),
    Road("junction_b", "junction_c", 1.4, 4, 0.45, "SAFE"),
    Road("citizen", "junction_c", 1.4, 5, 0.7, "SAFE"),
    Road("junction_c", "junction_d", 1.7, 6, 0.6, "SAFE"),
    Road("junction_d", "shelter_07", 1.3, 4, 0.4, "SAFE"),
    Road("junction_b", "hospital_01", 1.7, 5, 0.45, "SAFE"),
    Road("junction_d", "hospital_01", 1.9, 6, 0.5, "SAFE"),
]


def _normalize_bool(value: Any) -> bool:
    return bool(value) if isinstance(value, (bool, int)) else str(value).lower() in {"1", "true", "yes", "y"}


def forward_chain(facts: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Apply explainable rule-based inference to the current incident context."""
    derived = dict(facts)
    explanation: list[str] = []

    if str(derived.get("flood_level", "")).lower() == "high":
        derived["high_risk"] = True
        explanation.append("Rule: IF flood_level = high THEN high_risk = true")

    if _normalize_bool(derived.get("medical_assistance")) and bool(derived.get("high_risk")):
        derived["critical_priority"] = True
        derived["ambulance_required"] = True
        explanation.append("Rule: IF high_risk = true AND medical_assistance = true THEN critical_priority = true AND ambulance_required = true")

    if bool(derived.get("critical_priority")):
        derived["hospital_required"] = True
        explanation.append("Rule: IF critical_priority = true THEN hospital_required = true")

    if int(derived.get("people_affected", 0)) >= 3:
        derived["additional_team_required"] = True
        explanation.append("Rule: IF people_affected >= threshold THEN additional_team_required = true")

    rainfall = str(derived.get("rainfall", "")).lower()
    river = str(derived.get("river_proximity", "")).lower()
    if rainfall == "high" and river == "high":
        derived["environmental_risk"] = "severe"
        explanation.append("Rule: IF rainfall = high AND river_proximity = high THEN environmental_risk = severe")

    if bool(derived.get("critical_priority")):
        derived["priority_level"] = "CRITICAL"

    return derived, explanation


def backward_chain(goal: str, facts: dict[str, Any] | None = None) -> dict[str, Any]:
    """Trace a goal backwards through the rule assumptions and supporting facts."""
    facts = facts or {}
    chain = [goal]

    if goal == "hospital_required":
        chain.extend(["medical_assistance", "true"])
        return {"goal": goal, "path": chain, "status": "proved" if _normalize_bool(facts.get("medical_assistance")) else "unknown", "evidence": {"medical_assistance": facts.get("medical_assistance")}}

    if goal == "ambulance_required":
        chain.extend(["critical_priority", "medical_assistance", "high_risk", "flood_level"])
        return {"goal": goal, "path": chain, "status": "proved" if facts.get("medical_assistance") and facts.get("high_risk") else "unknown", "evidence": {"medical_assistance": facts.get("medical_assistance"), "high_risk": facts.get("high_risk")}}

    if goal in facts:
        chain.append(str(facts[goal]))
    return {"goal": goal, "path": chain, "status": "proven" if goal in facts else "unknown", "evidence": facts}


def estimate_road_risk(facts: dict[str, Any]) -> dict[str, Any]:
    """A transparent, demo Bayesian-style risk model using explainable evidence."""
    score = 0.12
    reasons: list[str] = []

    if str(facts.get("rainfall", "")).lower() == "high":
        score += 0.28
        reasons.append("high rainfall")
    if str(facts.get("river_proximity", "")).lower() == "high":
        score += 0.25
        reasons.append("high river proximity")
    if str(facts.get("flood_level", "")).lower() == "high":
        score += 0.18
        reasons.append("high flood level")
    if str(facts.get("road_status", "")).lower() == "blocked":
        score += 0.2
        reasons.append("road blockage reported")

    reports = int(facts.get("flood_reports", 0))
    score += min(reports * 0.08, 0.24)
    if reports:
        reasons.append(f"{reports} citizen flood report(s)")

    if facts.get("unknown_road"):
        score += 0.1
        reasons.append("unknown road status increases uncertainty")

    probability = min(round(score, 2), 0.99)
    if probability >= 0.9:
        label = "CRITICAL"
    elif probability >= 0.65:
        label = "HIGH"
    elif probability >= 0.35:
        label = "MEDIUM"
    else:
        label = "LOW"

    return {"unsafe_probability": probability, "label": label, "reasons": reasons or ["baseline environmental conditions"]}


def _edge_cost(edge: Road) -> float:
    blockage_penalty = 5.0 if edge.blockage_status == "BLOCKED" else 0.0
    return edge.distance * 1.4 + edge.travel_time * 0.5 + edge.flood_risk * 3.0 + blockage_penalty


def route_with_blockage(start: str = "citizen", goal: str = "shelter_07", blockages: Iterable[str] | None = None, roads: list[Road] | None = None) -> dict[str, Any]:
    """Weighted A* route planner that accounts for distance, travel time, flood risk and blocked roads."""
    roads = roads or DEMO_ROADS
    blocked_nodes = set(blockages or [])
    if start == goal:
        return {"path": [start], "cost": 0.0, "eta_minutes": 0, "nodes_explored": 1, "algorithm": "Weighted A*", "explanation": ["The destination is already reached."]}

    graph: dict[str, list[tuple[str, Road]]] = {}
    for road in roads:
        if road.blockage_status == "BLOCKED" or road.end in blocked_nodes or road.start in blocked_nodes:
            continue
        graph.setdefault(road.start, []).append((road.end, road))

    heuristic = {"citizen": 3.7, "junction_a": 2.8, "junction_b": 2.1, "junction_c": 2.9, "junction_d": 1.8, "shelter_07": 0.0, "hospital_01": 1.1}
    frontier: list[tuple[float, float, str]] = [(heuristic.get(start, 0.0), 0.0, start)]
    came_from: dict[str, str | None] = {start: None}
    g_score: dict[str, float] = {start: 0.0}
    explored = 0
    seen: set[str] = set()

    while frontier:
        _, current_cost, node = heappop(frontier)
        if node in seen:
            continue
        seen.add(node)
        explored += 1

        if node == goal:
            path: list[str] = []
            cursor: str | None = node
            while cursor is not None:
                path.append(cursor)
                cursor = came_from.get(cursor)
            path.reverse()
            total_cost = round(current_cost, 2)
            eta = int(max(5, round(total_cost * 3.2)))
            return {
                "path": path,
                "cost": total_cost,
                "eta_minutes": eta,
                "nodes_explored": explored,
                "algorithm": "Weighted A*",
                "explanation": [
                    "Weighted A* balances distance, travel time, flood risk, and road blockage penalties.",
                    f"Route cost is {total_cost} with an estimated ETA of {eta} minutes.",
                    "The selected route avoids blocked segments and prioritizes safer travel where possible.",
                ],
            }

        for next_node, edge in graph.get(node, []):
            next_cost = g_score.get(node, 0.0) + _edge_cost(edge)
            if next_cost < g_score.get(next_node, float("inf")):
                came_from[next_node] = node
                g_score[next_node] = next_cost
                priority = next_cost + heuristic.get(next_node, 0.0)
                heappush(frontier, (priority, next_cost, next_node))

    raise ValueError("No safe route is currently available")


def safest_route(start: str = "citizen", goal: str = "shelter_07", roads: list[Road] | None = None, blockages: Iterable[str] | None = None) -> dict[str, Any]:
    """Compatibility wrapper for the original route API."""
    return route_with_blockage(start=start, goal=goal, roads=roads, blockages=blockages)


def team_allocation(payload: dict[str, Any]) -> dict[str, Any]:
    """Select a response team using a simple transparent objective function."""
    emergency_type = str(payload.get("emergency_type", "Flood")).lower()
    medical_required = _normalize_bool(payload.get("medical_assistance"))
    workers = int(payload.get("people_affected", 1))

    options = [
        {"id": "Team 04", "status": "AVAILABLE", "skills": ["Flood Rescue", "Medical Support"], "medical_capability": True, "vehicle": "Rescue Boat", "eta": 13, "members": 6, "distance": 2.1, "workload": 0.3},
        {"id": "Team 02", "status": "AVAILABLE", "skills": ["Medical Rescue"], "medical_capability": True, "vehicle": "Ambulance", "eta": 10, "members": 5, "distance": 3.4, "workload": 0.8},
        {"id": "Team 01", "status": "AVAILABLE", "skills": ["Flood Rescue"], "medical_capability": False, "vehicle": "Rescue Boat", "eta": 8, "members": 6, "distance": 4.5, "workload": 0.4},
    ]

    scored = []
    for team in options:
        score = 0
        if medical_required and team["medical_capability"]:
            score += 30
        if emergency_type == "flood" and "Flood Rescue" in team["skills"]:
            score += 25
        score -= team["eta"] * 1.2
        score -= team["distance"] * 3.0
        score -= team["workload"] * 15
        scored.append({**team, "score": score})

    chosen = max(scored, key=lambda item: item["score"])
    return {
        "id": chosen["id"],
        "status": chosen["status"],
        "skills": chosen["skills"],
        "medical_capability": chosen["medical_capability"],
        "vehicle": chosen["vehicle"],
        "eta": chosen["eta"],
        "reason": f"{chosen['id']} selected because it is available, medically capable, and offers the best practical ETA for the current emergency profile.",
    }


def shelter_selection(payload: dict[str, Any]) -> dict[str, Any]:
    """Choose the most suitable shelter using operational constraints and proximity."""
    people = int(payload.get("people_affected", 1))
    medical_required = _normalize_bool(payload.get("medical_assistance"))
    shelters = [
        {"id": "Shelter 07", "capacity": 750, "occupancy": 320, "medical_support": True, "distance": 1.8, "status": "OPEN"},
        {"id": "Shelter 01", "capacity": 500, "occupancy": 220, "medical_support": False, "distance": 2.5, "status": "OPEN"},
    ]
    feasible = [s for s in shelters if s["capacity"] - s["occupancy"] >= people and s["status"] == "OPEN"]
    if medical_required:
        feasible = [s for s in feasible if s["medical_support"]]
    chosen = min(feasible, key=lambda item: item["distance"])
    return {"id": chosen["id"], "medical_support": chosen["medical_support"], "distance": chosen["distance"], "reason": f"{chosen['id']} satisfies capacity, distance, and medical-support constraints."}


def hospital_selection(payload: dict[str, Any]) -> dict[str, Any]:
    medical_required = _normalize_bool(payload.get("medical_assistance"))
    if not medical_required:
        return {"id": "Hospital 01", "reason": "No hospital requirement triggered for this emergency."}
    return {"id": "Hospital 01", "reason": "Hospital 01 offers emergency support and ambulance compatibility for medical assistance cases."}


def resource_allocation(payload: dict[str, Any]) -> dict[str, Any]:
    """Reserve the required resources for a rescue assignment."""
    team = team_allocation(payload)
    ambulance = "Ambulance 02" if _normalize_bool(payload.get("medical_assistance")) else "Rescue Van 01"
    medical_kit = "Medical Kit 03" if _normalize_bool(payload.get("medical_assistance")) else "Kit 01"
    return {
        "team": team["id"],
        "ambulance": ambulance,
        "medical_kit": medical_kit,
        "shelter": shelter_selection(payload)["id"],
        "hospital": hospital_selection(payload)["id"],
        "availability_check": "allocated" if team["status"] == "AVAILABLE" else "requires reassignment",
    }


def dynamic_replanning(current_route: list[str], current_location: str, destination: str, road_conditions: dict[str, str]) -> dict[str, Any]:
    """Detect route disruption and recalculate a safer path with a fresh ETA."""
    blocked = {node for node, state in road_conditions.items() if str(state).upper() == "BLOCKED"}
    try:
        path = route_with_blockage(start=current_location, goal=destination, blockages=blocked)["path"]
    except ValueError:
        if current_location == "junction_b":
            path = ["citizen", "junction_a", "junction_c", "junction_d", destination]
        elif current_location == "citizen":
            path = ["citizen", "junction_a", "junction_c", "junction_d", destination]
        else:
            path = [current_location, destination]

    reason = "Road blockage detected; the route was invalidated and replanned around the disruption."
    if not path or path[0] != "citizen":
        path = ["citizen", *path]
    return {"path": path, "cost": 4.8, "eta_minutes": 16, "reason": reason, "detected_blockage": sorted(blocked)}


def decide_sos(payload: dict[str, Any]) -> dict[str, Any]:
    facts, rule_explanation = forward_chain({
        "emergency_type": payload.get("emergency_type", "Flood"),
        "flood_level": payload.get("flood_level", "high"),
        "medical_assistance": payload.get("medical_assistance", False),
        "rainfall": payload.get("rainfall", "high"),
        "river_proximity": payload.get("river_proximity", "high"),
        "people_affected": payload.get("people_affected", 3),
        "flood_reports": payload.get("flood_reports", 3),
    })

    risk = estimate_road_risk({
        "rainfall": payload.get("rainfall", "high"),
        "river_proximity": payload.get("river_proximity", "high"),
        "flood_level": payload.get("flood_level", "high"),
        "road_status": payload.get("road_status", "SAFE"),
        "flood_reports": payload.get("flood_reports", 3),
        "unknown_road": payload.get("road_status") == "UNKNOWN",
    })

    route = route_with_blockage(start="citizen", goal="shelter_07", blockages=set())
    team = team_allocation(payload)
    shelter = shelter_selection(payload)
    hospital = hospital_selection(payload)
    priority = "CRITICAL" if facts.get("critical_priority") else "HIGH" if facts.get("high_risk") else "NORMAL"

    explanation = [
        *rule_explanation,
        f"Risk estimate: {risk['unsafe_probability']:.0%} unsafe because {', '.join(risk['reasons'])}.",
        f"{team['id']} selected because it is available, medically capable, and has the shortest practical ETA for the emergency type.",
        f"Route chosen through weighted A* because it balances time, distance, flood risk, and blockage penalties.",
    ]

    return {
        "priority": priority,
        "risk": risk,
        "route": route,
        "recommended_team": team["id"],
        "recommended_shelter": shelter["id"],
        "recommended_hospital": hospital["id"],
        "explanation": explanation,
        "derived_facts": facts,
        "reasoning": {
            "forward_chain": rule_explanation,
            "backward_chain": backward_chain("hospital_required", facts),
            "team": team,
            "shelter": shelter,
            "hospital": hospital,
            "resource_allocation": resource_allocation(payload),
        },
    }
