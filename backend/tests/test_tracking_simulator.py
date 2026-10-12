import asyncio

import app.main as main
from fastapi.testclient import TestClient


def test_tracking_simulator_emits_positions_and_arrives(monkeypatch):
    client = TestClient(main.app)
    response = client.post("/api/sos", json={"emergency_type": "Flood", "medical_assistance": True, "people_affected": 3})
    sos_id = response.json()["data"]["id"]
    events = []

    async def no_wait(_seconds):
        return None

    async def capture(event, payload, sos_id=None):
        events.append((event, payload))

    monkeypatch.setattr(main.asyncio, "sleep", no_wait)
    monkeypatch.setattr(main, "broadcast_event", capture)
    asyncio.run(main._track_sos(sos_id))

    position_events = [payload for event, payload in events if event == "team_position_updated"]
    assert len(position_events) == 20
    assert position_events[0]["progress"] < position_events[-1]["progress"]
    assert position_events[-1]["progress"] == 1
    assert main.repo.sos_requests[sos_id]["status"] == "ARRIVED"
