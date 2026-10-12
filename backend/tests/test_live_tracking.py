from app.main import _route_progress, app, repo
from fastapi.testclient import TestClient


def test_route_progress_uses_geometry_and_step_names():
    route = {
        "distance_m": 1000,
        "duration_s": 120,
        "geometry": {"type": "LineString", "coordinates": [[77.5946, 12.9716], [77.5960, 12.9770], [77.5960, 12.9838]]},
        "steps": [{"name": "Kasturba Road"}, {"name": "Queen's Road"}],
    }
    progress = _route_progress(route, 0.25)
    assert progress["distance_travelled_m"] > 0
    assert progress["distance_remaining_m"] > 0
    assert progress["current_road"] == "Kasturba Road"
    assert progress["next_road"] == "Queen's Road"
    assert 12.9716 < progress["latitude"] < 12.9838


def test_tracking_endpoint_exposes_route_state_and_timeline():
    client = TestClient(app)
    response = client.post("/api/sos", json={"emergency_type": "Flood", "medical_assistance": True, "people_affected": 3})
    assert response.status_code == 200
    sos_id = response.json()["data"]["id"]

    tracking = client.get(f"/api/sos/{sos_id}/tracking")
    assert tracking.status_code == 200
    data = tracking.json()["data"]
    assert data["route_status"] in {"ROUTE CALCULATED", "DEMO FALLBACK"}
    assert data["timeline"]
    assert data["tracking"]["distance_remaining_m"] >= 0


def test_complete_endpoint_keeps_sos_and_releases_team():
    client = TestClient(app)
    response = client.post("/api/sos", json={"emergency_type": "Flood", "medical_assistance": True, "people_affected": 3})
    sos_id = response.json()["data"]["id"]

    completed = client.post(f"/api/sos/{sos_id}/complete")
    assert completed.status_code == 200
    assert completed.json()["data"]["status"] == "RESOLVED"
    assert completed.json()["data"]["route_status"] == "RESCUE COMPLETED"
    assert client.get(f"/api/sos/{sos_id}").status_code == 200
    assert repo.teams["Team 04"]["status"] == "AVAILABLE"
