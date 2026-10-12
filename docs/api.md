# API surface

- `GET /health`
- `POST /api/sos`
- `GET /api/sos/{sos_id}`
- `GET /api/officer/dashboard`
- `WS /ws/officer/{officer_id}`

All REST responses use `{success, data, message}` in the demo. `POST /api/sos` accepts emergency type, severity, description, coordinates, affected people, medical need, and explicit demo evidence fields. The dashboard WebSocket emits `connected` and `sos.created` events.
