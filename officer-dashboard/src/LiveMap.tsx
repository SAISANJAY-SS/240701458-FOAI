import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

type Sos = {
  id: string;
  emergency_type: string;
  description: string;
  people_affected: number;
  latitude?: number;
  longitude?: number;
  status?: string;
  assigned_team?: string;
  recommended_shelter?: string;
  team_location?: { latitude: number; longitude: number; simulated?: boolean };
  shelter_location?: { latitude: number; longitude: number };
  route?: {
    success: boolean;
    provider: string;
    algorithm: string;
    distance_km: number;
    eta_minutes: number;
    geometry?: { type: string; coordinates: [number, number][] };
    alternatives?: Array<{ geometry?: { type: string; coordinates: [number, number][] } }>;
  };
  ai_decision?: {
    priority?: string;
    recommended_team?: string;
    recommended_shelter?: string;
    route?: { eta_minutes?: number };
    risk?: { label?: string };
  };
};

type Props = { sos: Sos[] };
const defaultCenter: L.LatLngExpression = [12.9716, 77.5946];

function createIcon(label: string, background: string) {
  return L.divIcon({
    className: '',
    html: `<div class="live-marker" style="--marker-color:${background}"><span>${label}</span></div>`,
    iconSize: [48, 48],
    iconAnchor: [24, 24],
    popupAnchor: [0, -24],
  });
}

function animateMarker(marker: L.Marker, target: L.LatLngExpression) {
  const start = marker.getLatLng();
  const end = L.latLng(target);
  const started = performance.now();
  const duration = 700;
  const frame = (now: number) => {
    const amount = Math.min((now - started) / duration, 1);
    marker.setLatLng([start.lat + (end.lat - start.lat) * amount, start.lng + (end.lng - start.lng) * amount]);
    if (amount < 1) requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}

export default function LiveMap({ sos }: Props) {
  const mapRef = useRef<L.Map | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const teamMarkerRef = useRef<L.Marker | null>(null);
  const [followTeam, setFollowTeam] = useState(false);
  const active = sos[0];

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, { center: defaultCenter, zoom: 13, zoomControl: true });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap contributors', maxZoom: 19 }).addTo(map);
    mapRef.current = map;
    const timer = window.setTimeout(() => map.invalidateSize(), 200);
    return () => { window.clearTimeout(timer); map.remove(); mapRef.current = null; teamMarkerRef.current = null; };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !active) return;
    map.eachLayer((layer) => { if (layer instanceof L.Marker || layer instanceof L.Polyline) map.removeLayer(layer); });
    teamMarkerRef.current = null;

    const citizen: L.LatLngTuple = [active.latitude ?? 12.9716, active.longitude ?? 77.5946];
    const shelter: L.LatLngTuple = active.shelter_location ? [active.shelter_location.latitude, active.shelter_location.longitude] : citizen;
    const team: L.LatLngTuple = active.team_location ? [active.team_location.latitude, active.team_location.longitude] : citizen;
    const roadRoute: L.LatLngTuple[] = (active.route?.geometry?.coordinates || []).map(([longitude, latitude]) => [latitude, longitude]);
    const primaryRoute: L.LatLngTuple[] = roadRoute.length ? roadRoute : [citizen, shelter];

    const citizenMarker = L.marker(citizen, { icon: createIcon('SOS', '#dc2626') }).addTo(map);
    citizenMarker.bindPopup(`<strong>${active.id}</strong><br/>${active.emergency_type}<br/>Priority: ${active.ai_decision?.priority || 'PENDING'}`);
    const teamMarker = L.marker(team, { icon: createIcon('🚑', '#168aad') }).addTo(map);
    teamMarkerRef.current = teamMarker;
    teamMarker.bindTooltip(`${active.assigned_team || active.ai_decision?.recommended_team || 'Team'} · ${active.status || 'ASSIGNED'}`, { permanent: true, direction: 'bottom', offset: [0, 18], className: 'team-label' });
    const shelterMarker = L.marker(shelter, { icon: createIcon('SHELTER', '#2f9e44') }).addTo(map);
    shelterMarker.bindPopup(`<strong>${active.recommended_shelter || active.ai_decision?.recommended_shelter || 'Shelter'}</strong><br/>Destination`);

    (active.route?.alternatives || []).forEach((alternative) => {
      const coordinates = alternative.geometry?.coordinates?.map(([longitude, latitude]): L.LatLngTuple => [latitude, longitude]);
      if (coordinates?.length) L.polyline(coordinates, { color: '#64748b', weight: 3, opacity: 0.45, dashArray: '5, 8' }).addTo(map);
    });
    L.polyline(primaryRoute, { color: active.route?.success ? '#38bdf8' : '#f59e0b', weight: 6, opacity: 0.92 }).addTo(map);

    if (followTeam) map.setView(team, Math.max(map.getZoom(), 15), { animate: true });
    else map.fitBounds(L.latLngBounds([citizen, team, shelter]), { padding: [50, 50], maxZoom: 14 });
  }, [active, followTeam]);

  useEffect(() => {
    if (!teamMarkerRef.current || !active?.team_location) return;
    const target: L.LatLngTuple = [active.team_location.latitude, active.team_location.longitude];
    animateMarker(teamMarkerRef.current, target);
    if (followTeam && mapRef.current) mapRef.current.panTo(target, { animate: true, duration: 0.7 });
  }, [active?.team_location?.latitude, active?.team_location?.longitude, followTeam]);

  const fitRoute = () => {
    if (!mapRef.current || !active) return;
    const coordinates = active.route?.geometry?.coordinates?.map(([longitude, latitude]) => [latitude, longitude] as L.LatLngTuple) || [];
    if (coordinates.length) mapRef.current.fitBounds(L.latLngBounds(coordinates), { padding: [50, 50] });
  };
  const centerTeam = () => { if (mapRef.current && active?.team_location) mapRef.current.setView([active.team_location.latitude, active.team_location.longitude], 16); };
  const centerSos = () => { if (mapRef.current && active) mapRef.current.setView([active.latitude ?? 12.9716, active.longitude ?? 77.5946], 16); };

  return <div className="live-map-shell">
    <div ref={containerRef} className="live-map-container" />
    <div className="map-navigation-card">
      <strong>{active?.route?.success ? 'REAL ROAD ROUTE' : 'DEMO FALLBACK'}</strong>
      <span>{active?.route?.distance_km ?? 0} km · {active?.route?.eta_minutes ?? 0} min</span>
      <span>{active?.route?.provider || 'ROUTE UNAVAILABLE'}</span>
      <label><input type="checkbox" checked={followTeam} onChange={(event) => setFollowTeam(event.target.checked)} /> Follow team</label>
    </div>
    <div className="map-action-bar">
      <button onClick={fitRoute}>Fit route</button><button onClick={centerTeam}>Center team</button><button onClick={centerSos}>Center SOS</button>
    </div>
  </div>;
}
