import { useEffect, useState } from "react";
import LiveMap from "./LiveMap";
import "./styles.css";

type Page =
  | "overview"
  | "map"
  | "sos"
  | "teams"
  | "shelters"
  | "ai";

type Sos = {
  id: string;
  status: string;
  created_at: string;
  citizen_role?: string;
  emergency_type: string;
  severity?: string;
  description: string;
  latitude: number;
  longitude: number;
  people_affected: number;
  medical_assistance: boolean;
  flood_level?: string;
  rainfall?: string;
  river_proximity?: string;
  flood_reports?: number;
  team_location?: { latitude: number; longitude: number; simulated?: boolean };
  shelter_location?: { latitude: number; longitude: number };
  route?: RoadRoute;
  route_status?: string;
  assigned_team?: string;
  recommended_shelter?: string;
  timeline?: TimelineItem[];
  tracking?: TrackingState;
  ai_decision?: {
    priority: string;
    risk: {
      unsafe_probability: number;
      label: string;
      reasons: string[];
    };
    route: {
      path: string[];
      cost: number;
      eta_minutes: number;
    };
    recommended_team: string;
    recommended_shelter: string;
    recommended_hospital?: string;
    explanation: string[];
    derived_facts: Record<string, unknown>;
  };
};

type TrackingState = {
  progress: number;
  distance_travelled_m: number;
  distance_remaining_m: number;
  eta_minutes: number;
  current_road?: string | null;
  next_road?: string | null;
  latitude?: number;
  longitude?: number;
  simulated?: boolean;
};

type TimelineItem = { timestamp: string; label: string; simulated?: boolean };

type RoadRoute = {
  success: boolean;
  provider: string;
  algorithm: string;
  distance_m: number;
  distance_km: number;
  duration_s: number;
  eta_minutes: number;
  geometry: { type: "LineString"; coordinates: [number, number][] };
  steps: Array<Record<string, unknown>>;
  alternatives: RoadRoute[];
  error?: string;
};

type Dashboard = {
  sos: Sos[];
  connected: boolean;
};

const API_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

function App() {
  const [activePage, setActivePage] = useState<Page>("overview");

  const [dashboard, setDashboard] = useState<Dashboard>({
    sos: [],
    connected: false,
  });

  const [selectedSos, setSelectedSos] = useState<Sos | null>(null);

  const mergeSos = (incoming: Sos) => {
    setDashboard((previous) => {
      const exists = previous.sos.some((sos) => sos.id === incoming.id);
      return {
        ...previous,
        sos: exists
          ? previous.sos.map((sos) => sos.id === incoming.id ? { ...sos, ...incoming } : sos)
          : [incoming, ...previous.sos],
      };
    });
  };

  /*
   * ---------------------------------------------------------
   * LOAD DASHBOARD DATA
   * ---------------------------------------------------------
   */

  const loadDashboard = async () => {
    try {
      const response = await fetch(`${API_URL}/api/dashboard`);

      if (!response.ok) {
        throw new Error("Failed to load dashboard");
      }

      const result = await response.json();

      setDashboard((previous) => ({
        ...previous,
        sos: result.data?.sos || result.sos || [],
      }));
    } catch (error) {
      console.error("Dashboard loading error:", error);
    }
  };

  useEffect(() => {
    if (selectedSos) {
      const refreshed = dashboard.sos.find((sos) => sos.id === selectedSos.id);
      if (refreshed) setSelectedSos(refreshed);
    }
  }, [dashboard.sos]);

  /*
   * ---------------------------------------------------------
   * WEBSOCKET CONNECTION
   * ---------------------------------------------------------
   */

  useEffect(() => {
    loadDashboard();

    const wsUrl = API_URL.replace(/^http/, "ws") + "/ws";

    let socket: WebSocket | null = null;

    try {
      socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        console.log("WebSocket connected");

        setDashboard((previous) => ({
          ...previous,
          connected: true,
        }));
      };

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);

          console.log("WebSocket message:", message);

          const eventName = String(message.event || message.type || "").toLowerCase();

          if (eventName === "sos_created") {
            mergeSos(message.data);
          }

          if (eventName === "dashboard_update") {
            loadDashboard();
          }

          if (["route_calculated", "route_updated"].includes(eventName)) {
            const { sos_id: sosId, route } = message.data || {};
            setDashboard((previous) => ({
              ...previous,
              sos: previous.sos.map((sos) => sos.id === sosId ? { ...sos, route, route_status: eventName === "route_updated" ? "ALTERNATIVE ROUTE" : route?.success ? "ROUTE CALCULATED" : "DEMO FALLBACK" } : sos),
            }));
          }

          if (eventName === "team_position_updated") {
            const { sos_id: sosId, ...tracking } = message.data || {};
            setDashboard((previous) => ({
              ...previous,
              sos: previous.sos.map((sos) => sos.id === sosId ? {
                ...sos,
                team_location: { latitude: tracking.latitude, longitude: tracking.longitude, simulated: true },
                tracking,
                route_status: "TEAM EN ROUTE",
                status: "TEAM EN ROUTE",
              } : sos),
            }));
          }

          if (eventName === "team_departed") {
            const sosId = message.data?.sos_id;
            setDashboard((previous) => ({ ...previous, sos: previous.sos.map((sos) => sos.id === sosId ? { ...sos, status: "TEAM EN ROUTE", route_status: "TEAM EN ROUTE" } : sos) }));
          }

          if (eventName === "team_arrived") {
            const sosId = message.data?.sos_id;
            setDashboard((previous) => ({ ...previous, sos: previous.sos.map((sos) => sos.id === sosId ? { ...sos, status: "ARRIVED", route_status: "ARRIVED" } : sos) }));
          }

          if (eventName === "rescue_completed") {
            const sosId = message.data?.sos_id;
            setDashboard((previous) => ({ ...previous, sos: previous.sos.map((sos) => sos.id === sosId ? { ...sos, status: "RESOLVED", route_status: "RESCUE COMPLETED" } : sos) }));
          }

          if (eventName === "route_replanning" || eventName === "road_blocked") {
            const sosId = message.data?.sos_id;
            setDashboard((previous) => ({
              ...previous,
              sos: previous.sos.map((sos) => sos.id === sosId ? { ...sos, route_status: "ROUTE REPLANNING" } : sos),
            }));
          }
        } catch (error) {
          console.error(
            "WebSocket message parsing error:",
            error
          );
        }
      };

      socket.onclose = () => {
        console.log("WebSocket disconnected");

        setDashboard((previous) => ({
          ...previous,
          connected: false,
        }));
      };

      socket.onerror = (error) => {
        console.error("WebSocket error:", error);

        setDashboard((previous) => ({
          ...previous,
          connected: false,
        }));
      };
    } catch (error) {
      console.error("WebSocket connection error:", error);
    }

    return () => {
      socket?.close();
    };
  }, []);

  /*
   * ---------------------------------------------------------
   * OPEN FULL MAP EVENT
   * ---------------------------------------------------------
   */

  useEffect(() => {
    const handler = () => {
      setActivePage("map");
    };

    window.addEventListener("open-live-map", handler);

    return () => {
      window.removeEventListener("open-live-map", handler);
    };
  }, []);

  /*
   * ---------------------------------------------------------
   * SIDEBAR NAVIGATION
   * ---------------------------------------------------------
   */

  const navigateTo = (page: Page) => {
    setActivePage(page);
    setSelectedSos(null);
  };

  /*
   * ---------------------------------------------------------
   * PAGE TITLES
   * ---------------------------------------------------------
   */

  const pageTitles: Record<Page, string> = {
    overview: "Overview",
    map: "Live Disaster Map",
    sos: "SOS Requests",
    teams: "Response Teams",
    shelters: "Shelters & Hospitals",
    ai: "AI Decision Intelligence",
  };

  /*
   * ---------------------------------------------------------
   * METRIC CALCULATIONS
   * ---------------------------------------------------------
   */

  const activeSosCount = dashboard.sos.filter(
    (sos) =>
      sos.status !== "COMPLETED" &&
      sos.status !== "RESOLVED"
  ).length;

  const criticalCount = dashboard.sos.filter(
    (sos) =>
      sos.ai_decision?.priority === "CRITICAL"
  ).length;

  /*
   * ---------------------------------------------------------
   * RENDER CURRENT PAGE
   * ---------------------------------------------------------
   */

  const renderPage = () => {
    if (selectedSos) {
      return (
        <SosDetailsPage
          sos={selectedSos}
          onBack={() => setSelectedSos(null)}
        />
      );
    }

    switch (activePage) {
      case "overview":
        return (
          <OverviewPage
            dashboard={dashboard}
            onSelectSos={(sos) => setSelectedSos(sos)}
          />
        );

      case "map":
        return (
          <MapView dashboard={dashboard} />
        );

      case "sos":
        return (
          <SosRequestsPage
            dashboard={dashboard}
            onSelectSos={(sos) => setSelectedSos(sos)}
          />
        );

      case "teams":
        return <ResponseTeamsPage />;

      case "shelters":
        return <SheltersPage />;

      case "ai":
        return (
          <AIDecisionsPage dashboard={dashboard} />
        );

      default:
        return null;
    }
  };

  return (
    <div className="app-shell">

      {/* =====================================================
          SIDEBAR
          ===================================================== */}

      <aside className="sidebar">

        <div className="sidebar-logo">

          <div className="logo-icon">
            R
          </div>

          <div>
            <h1>ResQAI</h1>
            <span>Disaster Intelligence</span>
          </div>

        </div>

        <nav className="sidebar-nav">

          <button
            className={
              activePage === "overview"
                ? "nav-item active"
                : "nav-item"
            }
            onClick={() => navigateTo("overview")}
          >
            <span className="nav-icon">⌂</span>
            <span>Overview</span>
          </button>

          <button
            className={
              activePage === "map"
                ? "nav-item active"
                : "nav-item"
            }
            onClick={() => navigateTo("map")}
          >
            <span className="nav-icon">◉</span>
            <span>Live Map</span>
          </button>

          <button
            className={
              activePage === "sos"
                ? "nav-item active"
                : "nav-item"
            }
            onClick={() => navigateTo("sos")}
          >
            <span className="nav-icon">🚨</span>
            <span>SOS Requests</span>

            {activeSosCount > 0 && (
              <span className="nav-count">
                {activeSosCount}
              </span>
            )}
          </button>

          <button
            className={
              activePage === "teams"
                ? "nav-item active"
                : "nav-item"
            }
            onClick={() => navigateTo("teams")}
          >
            <span className="nav-icon">🚑</span>
            <span>Response Teams</span>
          </button>

          <button
            className={
              activePage === "shelters"
                ? "nav-item active"
                : "nav-item"
            }
            onClick={() => navigateTo("shelters")}
          >
            <span className="nav-icon">🏠</span>
            <span>Shelters & Hospitals</span>
          </button>

          <button
            className={
              activePage === "ai"
                ? "nav-item active"
                : "nav-item"
            }
            onClick={() => navigateTo("ai")}
          >
            <span className="nav-icon">✦</span>
            <span>AI Intelligence</span>
          </button>

        </nav>

        <div className="sidebar-bottom">

          <div className="system-status">

            <span
              className={
                dashboard.connected
                  ? "status-dot online"
                  : "status-dot"
              }
            />

            <div>
              <strong>
                {dashboard.connected
                  ? "Live System"
                  : "Offline"}
              </strong>

              <span>
                {dashboard.connected
                  ? "Real-time connected"
                  : "Connection unavailable"}
              </span>
            </div>

          </div>

          <div className="demo-label">
            DEMO MODE
          </div>

        </div>

      </aside>

      {/* =====================================================
          MAIN CONTENT
          ===================================================== */}

      <main className="main-content">

        {/* HEADER */}

        <header className="top-header">

          <div>
            <h2>{pageTitles[activePage]}</h2>

            <p>
              Emergency Response Command Center
            </p>
          </div>

          <div className="header-right">

            <div className="live-status">

              <span
                className={
                  dashboard.connected
                    ? "status-dot online"
                    : "status-dot"
                }
              />

              {dashboard.connected
                ? "Live link"
                : "Disconnected"}

            </div>

            <div className="officer-profile">

              <div className="profile-avatar">
                O
              </div>

              <div>
                <strong>Officer</strong>
                <span>Command Center</span>
              </div>

            </div>

          </div>

        </header>

        {/* PAGE */}

        <div className="page-container">
          {renderPage()}
        </div>

      </main>

    </div>
  );
}

/* ============================================================
   METRIC CARDS
   ============================================================ */

function MetricCards({
  dashboard,
}: {
  dashboard: Dashboard;
}) {
  const activeSos = dashboard.sos.filter(
    (sos) =>
      sos.status !== "COMPLETED" &&
      sos.status !== "RESOLVED"
  ).length;

  const critical = dashboard.sos.filter(
    (sos) =>
      sos.ai_decision?.priority === "CRITICAL"
  ).length;

  return (
    <div className="metric-grid">

      <div className="metric-card">

        <div className="metric-icon danger">
          🚨
        </div>

        <div>
          <span>Active SOS</span>
          <strong>{activeSos}</strong>
          <small>Emergency requests</small>
        </div>

      </div>

      <div className="metric-card">

        <div className="metric-icon critical">
          !
        </div>

        <div>
          <span>Critical</span>
          <strong>{critical}</strong>
          <small>Immediate attention</small>
        </div>

      </div>

      <div className="metric-card">

        <div className="metric-icon team">
          🚑
        </div>

        <div>
          <span>Teams Ready</span>
          <strong>10</strong>
          <small>Response teams</small>
        </div>

      </div>

      <div className="metric-card">

        <div className="metric-icon ambulance">
          +
        </div>

        <div>
          <span>Ambulances</span>
          <strong>8</strong>
          <small>Available units</small>
        </div>

      </div>

    </div>
  );
}

/* ============================================================
   OVERVIEW PAGE
   ============================================================ */

function OverviewPage({
  dashboard,
  onSelectSos,
}: {
  dashboard: Dashboard;
  onSelectSos: (sos: Sos) => void;
}) {
  return (
    <div className="page-content">

      <MetricCards dashboard={dashboard} />

      {/* =====================================================
          LIVE MAP
          ===================================================== */}

      <section className="panel overview-map-panel">

        <div className="panel-header">

          <div>
            <h2>Live Disaster Map</h2>

            <p>
              Real-time emergency, response team and
              shelter locations
            </p>
          </div>

          <button
            className="secondary-button"
            onClick={() => {
              window.dispatchEvent(
                new CustomEvent("open-live-map")
              );
            }}
          >
            Open Full Map
          </button>

        </div>

        <div className="overview-map">

          <LiveMap sos={dashboard.sos} />

        </div>

      </section>

      {/* =====================================================
          LOWER DASHBOARD
          ===================================================== */}

      <div className="overview-grid">

        {/* RECENT SOS */}

        <section className="panel">

          <div className="panel-header">

            <div>
              <h2>Recent SOS Requests</h2>

              <p>
                Latest citizen emergency reports
              </p>
            </div>

          </div>

          <div className="sos-list">

            {dashboard.sos.length === 0 ? (
              <div className="empty-state">
                No active SOS requests
              </div>
            ) : (
              dashboard.sos
                .slice(0, 5)
                .map((sos) => (

                  <button
                    key={sos.id}
                    className="sos-list-item"
                    onClick={() =>
                      onSelectSos(sos)
                    }
                  >

                    <div className="sos-icon">
                      🚨
                    </div>

                    <div className="sos-info">

                      <strong>
                        {sos.id}
                      </strong>

                      <span>
                        {sos.emergency_type}
                      </span>

                    </div>

                    <div className="sos-meta">

                      <span
                        className={`status-badge ${
                          sos.ai_decision?.priority?.toLowerCase() ||
                          "pending"
                        }`}
                      >
                        {sos.ai_decision?.priority ||
                          "PENDING"}
                      </span>

                      <span>
                        {sos.people_affected} people
                      </span>

                    </div>

                  </button>

                ))
            )}

          </div>

        </section>

        {/* AI SUMMARY */}

        <section className="panel">

          <div className="panel-header">

            <div>
              <h2>AI Decision Summary</h2>

              <p>
                Current emergency intelligence
              </p>
            </div>

          </div>

          {dashboard.sos.length > 0 &&
          dashboard.sos[0].ai_decision ? (

            <div className="ai-summary">

              <div className="ai-summary-row">
                <span>Priority</span>

                <strong>
                  {dashboard.sos[0].ai_decision.priority}
                </strong>
              </div>

              <div className="ai-summary-row">
                <span>Risk</span>

                <strong>
                  {dashboard.sos[0].ai_decision.risk.label}
                </strong>
              </div>

              <div className="ai-summary-row">
                <span>Unsafe Probability</span>

                <strong>
                  {Math.round(
                    dashboard.sos[0].ai_decision.risk
                      .unsafe_probability * 100
                  )}
                  %
                </strong>
              </div>

              <div className="ai-summary-row">
                <span>Recommended Team</span>

                <strong>
                  {
                    dashboard.sos[0].ai_decision
                      .recommended_team
                  }
                </strong>
              </div>

              <div className="ai-summary-row">
                <span>Recommended Shelter</span>

                <strong>
                  {
                    dashboard.sos[0].ai_decision
                      .recommended_shelter
                  }
                </strong>
              </div>

              <div className="ai-summary-row">
                <span>Estimated ETA</span>

                <strong>
                  {dashboard.sos[0].route?.eta_minutes ?? dashboard.sos[0].ai_decision.route.eta_minutes}{" "}
                  min
                </strong>
              </div>

            </div>

          ) : (

            <div className="empty-state">
              Waiting for AI decisions...
            </div>

          )}

        </section>

      </div>

    </div>
  );
}

/* ============================================================
   MAP PAGE
   ============================================================ */

function MapView({
  dashboard,
}: {
  dashboard: Dashboard;
}) {
  return (
    <div className="page-content">

      <section className="panel full-map-panel">

        <div className="panel-header">

          <div>
            <h2>Live Disaster Map</h2>

            <p>
              Monitor emergencies, rescue teams,
              shelters and routes
            </p>
          </div>

          <div className="map-status">

            <span className="status-dot online" />

            Live

          </div>

        </div>

        <div className="full-map-container">

          <LiveMap sos={dashboard.sos} />

        </div>

      </section>

    </div>
  );
}

/* ============================================================
   SOS REQUESTS PAGE
   ============================================================ */

function SosRequestsPage({
  dashboard,
  onSelectSos,
}: {
  dashboard: Dashboard;
  onSelectSos: (sos: Sos) => void;
}) {
  return (
    <div className="page-content">

      <section className="panel">

        <div className="panel-header">

          <div>
            <h2>Emergency Requests</h2>

            <p>
              Citizen SOS reports received by the
              command center
            </p>
          </div>

          <span className="count-label">
            {dashboard.sos.length} requests
          </span>

        </div>

        <div className="table-container">

          <table>

            <thead>
              <tr>
                <th>ID</th>
                <th>Type</th>
                <th>Priority</th>
                <th>People</th>
                <th>Medical</th>
                <th>Risk</th>
                <th>ETA</th>
                <th></th>
              </tr>
            </thead>

            <tbody>

              {dashboard.sos.map((sos) => (

                <tr key={sos.id}>

                  <td>
                    <strong>{sos.id}</strong>
                  </td>

                  <td>
                    {sos.emergency_type}
                  </td>

                  <td>

                    <span
                      className={`status-badge ${
                        sos.ai_decision?.priority?.toLowerCase() ||
                        "pending"
                      }`}
                    >
                      {sos.ai_decision?.priority ||
                        "PENDING"}
                    </span>

                  </td>

                  <td>
                    {sos.people_affected}
                  </td>

                  <td>
                    {sos.medical_assistance
                      ? "Required"
                      : "No"}
                  </td>

                  <td>
                    {sos.ai_decision?.risk?.label ||
                      "-"}
                  </td>

                  <td>
                    {sos.route?.eta_minutes ?? sos.ai_decision?.route?.eta_minutes
                      ? `${sos.route?.eta_minutes ?? sos.ai_decision?.route?.eta_minutes} min`
                      : "-"}
                  </td>

                  <td>

                    <button
                      className="table-button"
                      onClick={() =>
                        onSelectSos(sos)
                      }
                    >
                      View
                    </button>

                  </td>

                </tr>

              ))}

            </tbody>

          </table>

        </div>

      </section>

    </div>
  );
}

/* ============================================================
   SOS DETAILS
   ============================================================ */

function SosDetailsPage({
  sos,
  onBack,
}: {
  sos: Sos;
  onBack: () => void;
}) {
  const decision = sos.ai_decision;
  const navigationRoute = sos.route;

  const callTracking = async (path: string) => {
    await fetch(`${API_URL}/api/sos/${sos.id}/${path}`, { method: "POST" });
  };

  return (
    <div className="page-content">

      <button
        className="back-button"
        onClick={onBack}
      >
        ← Back to SOS Requests
      </button>

      <div className="details-grid">

        {/* BASIC INFORMATION */}

        <section className="panel">

          <div className="panel-header">

            <div>
              <h2>{sos.id}</h2>

              <p>
                Emergency request details
              </p>
            </div>

            <span
              className={`status-badge ${
                decision?.priority?.toLowerCase() ||
                "pending"
              }`}
            >
              {decision?.priority || "PENDING"}
            </span>

          </div>

          <div className="details-list">

            <div>
              <span>Emergency Type</span>
              <strong>{sos.emergency_type}</strong>
            </div>

            <div>
              <span>Description</span>
              <strong>{sos.description}</strong>
            </div>

            <div>
              <span>People Affected</span>
              <strong>{sos.people_affected}</strong>
            </div>

            <div>
              <span>Medical Assistance</span>
              <strong>
                {sos.medical_assistance
                  ? "Required"
                  : "Not Required"}
              </strong>
            </div>

            <div>
              <span>Latitude</span>
              <strong>{sos.latitude}</strong>
            </div>

            <div>
              <span>Longitude</span>
              <strong>{sos.longitude}</strong>
            </div>

          </div>

        </section>

        {/* AI DECISION */}

        <section className="panel">

          <div className="panel-header">

            <div>
              <h2>AI Decision</h2>

              <p>
                Explainable emergency reasoning
              </p>
            </div>

            <span className="ai-label">
              AI
            </span>

          </div>

          {decision ? (

            <div className="ai-detail">

              <div className="decision-highlight">

                <span>Priority</span>

                <strong>
                  {decision.priority}
                </strong>

              </div>

              <div className="decision-highlight">

                <span>Risk</span>

                <strong>
                  {decision.risk.label}
                </strong>

              </div>

              <div className="decision-highlight">

                <span>Unsafe Probability</span>

                <strong>
                  {Math.round(
                    decision.risk
                      .unsafe_probability * 100
                  )}
                  %
                </strong>

              </div>

              <div className="decision-highlight">

                <span>Recommended Team</span>

                <strong>
                  {decision.recommended_team}
                </strong>

              </div>

              <div className="decision-highlight">

                <span>Recommended Shelter</span>

                <strong>
                  {decision.recommended_shelter}
                </strong>

              </div>

              <div className="decision-highlight">

                <span>ETA</span>

                <strong>
                  {sos.route?.eta_minutes ?? decision.route.eta_minutes} min
                </strong>

              </div>

            </div>

          ) : (

            <div className="empty-state">
              AI decision not available
            </div>

          )}

        </section>

      </div>

      <section className="navigation-workspace">
        <div className="panel navigation-map-panel">
          <div className="panel-header">
            <div><h2>Live Rescue Tracking</h2><p>Simulated GPS follows the OSRM road geometry</p></div>
            <span className="status-badge assigned">{sos.route_status || "ROUTE CALCULATED"}</span>
          </div>
          <LiveMap sos={[sos]} />
        </div>
        <div className="navigation-stack">
          <NavigationPanel sos={sos} />
          <div className="navigation-actions">
            <button className="secondary-button" onClick={() => callTracking("start")}>Start tracking</button>
            <button className="table-button" onClick={() => callTracking("complete")}>Mark rescue complete</button>
          </div>
        </div>
      </section>

      {/* REASONING */}

      {decision && (

        <section className="panel reasoning-panel">

          <div className="panel-header">

            <div>
              <h2>AI Reasoning Chain</h2>

              <p>
                Explainable decision-making process
              </p>
            </div>

          </div>

          <div className="reasoning-list">

            {decision.explanation.map(
              (reason, index) => (

                <div
                  className="reasoning-item"
                  key={index}
                >

                  <div className="reasoning-number">
                    {index + 1}
                  </div>

                  <div>
                    {reason}
                  </div>

                </div>

              )
            )}

          </div>

        </section>

      )}

    </div>
  );
}

function NavigationPanel({ sos }: { sos: Sos }) {
  const route = sos.route;
  const tracking = sos.tracking;
  const steps = route?.steps || [];
  const namedSteps = steps.filter((step) => typeof step.name === "string" && step.name);
  const nextStep = namedSteps[0] as { name?: string; maneuver?: { type?: string; modifier?: string }; distance?: number } | undefined;
  const followingStep = namedSteps[1] as { name?: string; maneuver?: { type?: string; modifier?: string }; distance?: number } | undefined;
  const instruction = nextStep ? `${nextStep.maneuver?.modifier || nextStep.maneuver?.type || "Continue"} ${nextStep.name}` : "Road information unavailable";
  const progress = Math.round((tracking?.progress || 0) * 100);

  return <section className="panel navigation-panel">
    <div className="navigation-heading"><span className="eyebrow">LIVE RESCUE</span><strong>🚑 {sos.assigned_team || sos.ai_decision?.recommended_team || "Team"}</strong><span className="status-badge assigned">{sos.status}</span></div>
    <div className="navigation-metrics">
      <div><span>ETA</span><strong>{route?.success ? `${tracking?.eta_minutes ?? route.eta_minutes} min` : "Demo estimate"}</strong></div>
      <div><span>Distance</span><strong>{route?.distance_km ?? 0} km</strong></div>
      <div><span>Routing</span><strong>{route?.provider || "ROUTE UNAVAILABLE"}</strong></div>
    </div>
    <div className="progress-track"><span style={{ width: `${progress}%` }} /></div>
    <div className="progress-label"><span>{`${((tracking?.distance_travelled_m || 0) / 1000).toFixed(2)} km travelled`}</span><strong>{progress}%</strong></div>
    <div className="road-readout"><span>Current road</span><strong>{tracking?.current_road || "Road information unavailable"}</strong><span>Next road</span><strong>{tracking?.next_road || "Road information unavailable"}</strong></div>
    <div className="instruction-card"><span>NEXT ACTION</span><strong>↱ {instruction}</strong><small>{nextStep?.distance ? `${Math.round(nextStep.distance)} m` : "Distance unavailable"}</small>{followingStep && <em>Then: {followingStep.maneuver?.modifier || followingStep.maneuver?.type || "Continue"} {followingStep.name}</em>}</div>
    <div className="destination-readout"><span>Destination</span><strong>🏠 {sos.recommended_shelter || sos.ai_decision?.recommended_shelter || "Shelter"}</strong></div>
  </section>;
}

/* ============================================================
   RESPONSE TEAMS
   ============================================================ */

function ResponseTeamsPage() {
  const teams = [
    {
      id: "Team 01",
      status: "AVAILABLE",
      members: 6,
      specialty: "Flood Rescue",
      vehicle: "Rescue Boat",
      eta: "8 min",
    },
    {
      id: "Team 02",
      status: "AVAILABLE",
      members: 5,
      specialty: "Medical Rescue",
      vehicle: "Ambulance",
      eta: "10 min",
    },
    {
      id: "Team 03",
      status: "AVAILABLE",
      members: 7,
      specialty: "Urban Rescue",
      vehicle: "Rescue Van",
      eta: "12 min",
    },
    {
      id: "Team 04",
      status: "ASSIGNED",
      members: 6,
      specialty: "Flood + Medical",
      vehicle: "Rescue Boat",
      eta: "13 min",
    },
    {
      id: "Team 05",
      status: "AVAILABLE",
      members: 5,
      specialty: "Search & Rescue",
      vehicle: "Rescue Van",
      eta: "15 min",
    },
  ];

  return (
    <div className="page-content">

      <section className="panel">

        <div className="panel-header">

          <div>
            <h2>Response Teams</h2>

            <p>
              Rescue units and operational readiness
            </p>
          </div>

          <span className="count-label">
            10 teams
          </span>

        </div>

        <div className="team-grid">

          {teams.map((team) => (

            <div
              className="team-card"
              key={team.id}
            >

              <div className="team-card-header">

                <div className="team-avatar">
                  🚑
                </div>

                <span
                  className={`status-badge ${
                    team.status.toLowerCase()
                  }`}
                >
                  {team.status}
                </span>

              </div>

              <h3>{team.id}</h3>

              <p>{team.specialty}</p>

              <div className="team-details">

                <div>
                  <span>Members</span>
                  <strong>{team.members}</strong>
                </div>

                <div>
                  <span>Vehicle</span>
                  <strong>{team.vehicle}</strong>
                </div>

                <div>
                  <span>ETA</span>
                  <strong>{team.eta}</strong>
                </div>

              </div>

            </div>

          ))}

        </div>

      </section>

    </div>
  );
}

/* ============================================================
   SHELTERS & HOSPITALS
   ============================================================ */

function SheltersPage() {
  const shelters = [
    {
      id: "Shelter 01",
      name: "Community Relief Center",
      capacity: 500,
      occupied: 210,
      status: "OPEN",
      type: "Emergency Shelter",
    },
    {
      id: "Shelter 07",
      name: "Central Relief Shelter",
      capacity: 750,
      occupied: 320,
      status: "OPEN",
      type: "Emergency Shelter",
    },
    {
      id: "Shelter 12",
      name: "Government Relief Camp",
      capacity: 1000,
      occupied: 640,
      status: "OPEN",
      type: "Relief Camp",
    },
  ];

  const hospitals = [
    {
      name: "City General Hospital",
      emergency: true,
      beds: 34,
      ambulance: 5,
    },
    {
      name: "Central Medical Center",
      emergency: true,
      beds: 21,
      ambulance: 3,
    },
  ];

  return (
    <div className="page-content">

      <div className="two-column-layout">

        {/* SHELTERS */}

        <section className="panel">

          <div className="panel-header">

            <div>
              <h2>Emergency Shelters</h2>

              <p>
                Available evacuation locations
              </p>
            </div>

          </div>

          <div className="resource-list">

            {shelters.map((shelter) => (

              <div
                className="resource-card"
                key={shelter.id}
              >

                <div className="resource-icon">
                  🏠
                </div>

                <div className="resource-main">

                  <strong>{shelter.id}</strong>

                  <span>
                    {shelter.name}
                  </span>

                  <small>
                    {shelter.type}
                  </small>

                </div>

                <div className="resource-stats">

                  <strong>
                    {shelter.occupied}/
                    {shelter.capacity}
                  </strong>

                  <span>
                    occupants
                  </span>

                </div>

              </div>

            ))}

          </div>

        </section>

        {/* HOSPITALS */}

        <section className="panel">

          <div className="panel-header">

            <div>
              <h2>Hospitals</h2>

              <p>
                Emergency medical capacity
              </p>
            </div>

          </div>

          <div className="resource-list">

            {hospitals.map((hospital) => (

              <div
                className="resource-card"
                key={hospital.name}
              >

                <div className="resource-icon hospital">
                  +
                </div>

                <div className="resource-main">

                  <strong>
                    {hospital.name}
                  </strong>

                  <span>
                    Emergency department
                  </span>

                  <small>
                    {hospital.emergency
                      ? "Emergency services active"
                      : "Limited services"}
                  </small>

                </div>

                <div className="resource-stats">

                  <strong>
                    {hospital.beds}
                  </strong>

                  <span>
                    beds

                  </span>

                  <small>
                    🚑 {hospital.ambulance}
                  </small>

                </div>

              </div>

            ))}

          </div>

        </section>

      </div>

    </div>
  );
}

/* ============================================================
   AI DECISIONS PAGE
   ============================================================ */

function AIDecisionsPage({
  dashboard,
}: {
  dashboard: Dashboard;
}) {
  const sos = dashboard.sos[0];
  const decision = sos?.ai_decision;

  return (
    <div className="page-content">

      <section className="panel">

        <div className="panel-header">

          <div>
            <h2>AI Decision Intelligence</h2>

            <p>
              Explainable AI reasoning for disaster
              response decisions
            </p>
          </div>

          <span className="ai-label">
            AI ENGINE ACTIVE
          </span>

        </div>

        {!decision ? (

          <div className="empty-state">
            Waiting for an emergency decision...
          </div>

        ) : (

          <div className="ai-dashboard">

            {/* DECISION */}

            <div className="ai-decision-card">

              <span>Priority Decision</span>

              <strong>
                {decision.priority}
              </strong>

              <p>
                Derived using rule-based forward
                chaining.
              </p>

            </div>

            {/* BAYESIAN RISK */}

            <div className="ai-decision-card">

              <span>Bayesian Risk Estimate</span>

              <strong>
                {Math.round(
                  decision.risk
                    .unsafe_probability * 100
                )}
                %
              </strong>

              <p>
                {decision.risk.label} road safety
                probability.
              </p>

            </div>

            {/* SEARCH */}

            <div className="ai-decision-card">

              <span>Pathfinding</span>

              <strong>
                Weighted A*
              </strong>

              <p>
                Route cost:{" "}
                {decision.route.cost}
              </p>

            </div>

            {/* TEAM */}

            <div className="ai-decision-card">

              <span>Team Allocation</span>

              <strong>
                {decision.recommended_team}
              </strong>

              <p>
                Selected based on availability,
                capability and ETA.
              </p>

            </div>

          </div>

        )}

      </section>

      {decision && (

        <div className="ai-analysis-grid">

          {/* DERIVED FACTS */}

          <section className="panel">

            <div className="panel-header">

              <div>
                <h2>Derived Facts</h2>

                <p>
                  Knowledge-based reasoning state
                </p>
              </div>

            </div>

            <div className="facts-list">

              {Object.entries(
                decision.derived_facts
              ).map(([key, value]) => (

                <div
                  className="fact-row"
                  key={key}
                >

                  <span>
                    {key.replace(/_/g, " ")}
                  </span>

                  <strong>
                    {String(value)}
                  </strong>

                </div>

              ))}

            </div>

          </section>

          {/* RISK REASONS */}

          <section className="panel">

            <div className="panel-header">

              <div>
                <h2>Risk Factors</h2>

                <p>
                  Evidence used by the risk model
                </p>
              </div>

            </div>

            <div className="reasoning-list">

              {decision.risk.reasons.map(
                (reason, index) => (

                  <div
                    className="reasoning-item"
                    key={index}
                  >

                    <div className="reasoning-number">
                      {index + 1}
                    </div>

                    <div>
                      {reason}
                    </div>

                  </div>

                )
              )}

            </div>

          </section>

        </div>

      )}

    </div>
  );
}

export default App;