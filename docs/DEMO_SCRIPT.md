# ResQAI Demo Script

## 5–10 minute demo flow

### 1. Introduce the problem

"Emergency teams need to react quickly to floods, but decisions must be explainable and route-aware. ResQAI combines rule-based reasoning, risk assessment, and route planning to support this workflow."

### 2. Citizen creates SOS

Open the citizen app or submit a flood report via the API. The emergency includes high flood level, medical assistance, and multiple citizen reports.

### 3. AI analyzes the incident

The backend applies forward chaining and creates high-risk and critical-priority facts. The officer dashboard receives a live update.

### 4. Officer receives alert

The command center shows an active critical SOS, a recommended team, shelter, hospital, ETA, and route.

### 5. AI explains the decision

Show the explanation chain: flooding + medical need => critical priority and ambulance requirement; risk estimate based on rainfall, river proximity, and flood reports; route chosen by weighted A\*.

### 6. Team assignment

Assign Team 04 and update the team status to EN_ROUTE. This is visible in both the dashboard and the route map.

### 7. Live map and evidence

Open the map and highlight the SOS location, recommended team, shelter, and route overlay. This demonstrates that live operational context is visible to officers in real time.

### 8. Road blockage event

Trigger the Simulate Road Block action. The route through Junction B becomes invalid as the road is marked BLOCKED.

### 9. Dynamic replanning

The system recalculates the path and updates the ETA. Show the new route and the reason for the replanning.

### 10. Rescue completion

Mark the rescue as complete. The dashboard updates the SOS status to RESOLVED and frees the associated resource and team.

## Likely judge questions and concise answers

### Q: Why does the project use classical AI instead of a black-box model?

A: Because the system must explain every decision in a command-center environment. Officers need to understand why a team was selected, why a shelter was recommended, and why the route changed.

### Q: How does dynamic replanning work?

A: The backend checks road conditions, invalidates the affected route, and recalculates using the same weighted A\* logic with the new blockage constraints.

### Q: Is this production-ready AI?

A: It is a demo-first, explainable system intended for academic and hackathon demonstration. It is deterministic, transparent, and built around simulated disaster logic rather than external paid APIs.

### Q: What would scale next?

A: Add a real Postgres repository, real map data, weather feeds, and stronger multi-agent simulation while keeping the same explainable architecture.

## Demo commands

```bash
cd ResqAI
PYTHONPATH=backend .venv/bin/python -m uvicorn app.main:app --reload --port 8000
cd officer-dashboard
npm run dev
```

Then trigger the demo flood using the UI or:

```bash
curl -X POST http://localhost:8000/api/sos \
  -H 'Content-Type: application/json' \
  -d '{"emergency_type":"Flood","medical_assistance":true,"people_affected":3,"description":"Trapped in a flood","flood_level":"high","rainfall":"high","river_proximity":"high","flood_reports":3}'
```
