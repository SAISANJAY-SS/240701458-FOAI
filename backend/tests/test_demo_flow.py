from fastapi.testclient import TestClient

from app.ai_engine import dynamic_replanning, forward_chain, route_with_blockage, team_allocation
from app.main import app


def test_flood_sos_is_explainable_and_critical():
    client = TestClient(app)
    response = client.post("/api/sos", json={"emergency_type": "Flood", "medical_assistance": True, "people_affected": 3})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["ai_decision"]["priority"] == "CRITICAL"
    assert data["ai_decision"]["recommended_team"] == "Team 04"
    assert data["ai_decision"]["route"]["path"][-1] == "shelter_07"
    assert data["ai_decision"]["explanation"]


def test_forward_chaining_expands_facts_and_backwards_reasoning():
    facts, explanation = forward_chain({"flood_level": "high", "medical_assistance": True, "rainfall": "high", "river_proximity": "high"})
    assert facts["high_risk"] is True
    assert facts["critical_priority"] is True
    assert facts["ambulance_required"] is True
    assert facts["hospital_required"] is True
    assert explanation


def test_route_replanning_after_blockage_chooses_alternative():
    original = route_with_blockage("citizen", "shelter_07", blockages=set())
    replanned = dynamic_replanning(
        current_route=original["path"],
        current_location="junction_b",
        destination="shelter_07",
        road_conditions={"junction_b": "BLOCKED"},
    )
    assert replanned["reason"]
    assert replanned["path"][0] == "citizen"
    assert replanned["path"][-1] == "shelter_07"


def test_team_allocation_prefers_medical_capable_unit():
    team = team_allocation({"emergency_type": "Flood", "medical_assistance": True, "people_affected": 3})
    assert team["id"] == "Team 04"
    assert team["medical_capability"] is True
