CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), email TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL, role TEXT NOT NULL CHECK (role IN ('CITIZEN','OFFICER','RESCUE_TEAM','ADMIN','VOLUNTEER')),
  password_hash TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS sos_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID REFERENCES users(id),
  emergency_type TEXT NOT NULL, severity TEXT NOT NULL, description TEXT,
  people_affected INTEGER NOT NULL DEFAULT 1, medical_assistance BOOLEAN NOT NULL DEFAULT false,
  location geography(Point,4326) NOT NULL, status TEXT NOT NULL DEFAULT 'REQUEST_RECEIVED',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS sos_location_idx ON sos_requests USING GIST(location);
CREATE TABLE IF NOT EXISTS shelters (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name TEXT NOT NULL,
  location geography(Point,4326) NOT NULL, total_capacity INTEGER NOT NULL,
  occupied INTEGER NOT NULL DEFAULT 0, medical_facility BOOLEAN NOT NULL DEFAULT false,
  accessibility BOOLEAN NOT NULL DEFAULT false, status TEXT NOT NULL DEFAULT 'ACTIVE'
);
CREATE INDEX IF NOT EXISTS shelters_location_idx ON shelters USING GIST(location);
CREATE TABLE IF NOT EXISTS hospitals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name TEXT NOT NULL,
  location geography(Point,4326) NOT NULL, emergency_support BOOLEAN NOT NULL DEFAULT true,
  status TEXT NOT NULL DEFAULT 'OPEN'
);
CREATE TABLE IF NOT EXISTS rescue_teams (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name TEXT NOT NULL, team_type TEXT NOT NULL,
  location geography(Point,4326) NOT NULL, available BOOLEAN NOT NULL DEFAULT true,
  medical_capable BOOLEAN NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS ai_decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), sos_id UUID REFERENCES sos_requests(id) ON DELETE CASCADE,
  priority TEXT NOT NULL, risk JSONB NOT NULL, route JSONB NOT NULL, explanation JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), actor_id UUID REFERENCES users(id), action TEXT NOT NULL,
  previous_value JSONB, new_value JSONB, reason TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
