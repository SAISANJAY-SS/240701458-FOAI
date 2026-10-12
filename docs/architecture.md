# ResQAI architecture

The Flutter app submits citizen observations; it does not calculate priority. FastAPI owns authentication, validation, persistence boundaries, and WebSocket fanout. The classical AI engine receives facts and returns a decision object containing derived facts, weighted route, risk estimate, recommendation, and human-readable explanation. React renders that decision for authorized officers.

The current demo slice keeps request state in memory to remain runnable without external services. `database/schema.sql` is the PostgreSQL/PostGIS persistence contract for the next repository integration. This makes the absence of a database visible rather than silently pretending demo data is live.

## Decision flow

1. Forward chaining derives high risk, critical priority, ambulance need, and hospital need.
2. The risk module combines explicit demo evidence into a bounded, labeled estimate.
3. Weighted graph search chooses the lowest practical distance/risk cost.
4. The officer reviews and confirms; future assignment changes belong in the audit log.
5. WebSocket clients receive the same event envelope.
