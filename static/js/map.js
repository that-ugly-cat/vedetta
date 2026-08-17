'use strict';

const STATE_ICON = {
  AIRBORNE:    '✈️',
  GROUNDED:    '🛬',
  WALKING:     '🚶',
  SIGNAL_LOST: '📵',
  UNKNOWN:     '❓',
};

// ── marker icons ──────────────────────────────────────────────────────────────

function makeArrowIcon(deg, color) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 30 30">
    <g transform="rotate(${deg || 0}, 15, 15)">
      <polygon points="15,3 25,25 15,19 5,25"
               fill="${color || '#f5c542'}" stroke="white" stroke-width="2" stroke-linejoin="round"/>
    </g>
  </svg>`;
  return L.divIcon({ html: svg, className: '', iconSize: [30, 30], iconAnchor: [15, 15], popupAnchor: [0, -18] });
}

function makeCircleIcon(color) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 22 22">
    <circle cx="11" cy="11" r="8" fill="${color}" stroke="white" stroke-width="2.5"/>
  </svg>`;
  return L.divIcon({ html: svg, className: '', iconSize: [22, 22], iconAnchor: [11, 11], popupAnchor: [0, -14] });
}

function makeXIcon() {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 22 22">
    <circle cx="11" cy="11" r="9" fill="#ff5c5c" stroke="white" stroke-width="2"/>
    <line x1="6" y1="6" x2="16" y2="16" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
    <line x1="16" y1="6" x2="6" y2="16" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
  </svg>`;
  return L.divIcon({ html: svg, className: '', iconSize: [22, 22], iconAnchor: [11, 11], popupAnchor: [0, -14] });
}

function makeIcon(state, course_deg, color) {
  const c = color || '#4a9eff';
  switch (state) {
    case 'AIRBORNE':    return makeArrowIcon(course_deg, c);
    case 'GROUNDED':    return makeCircleIcon(c);
    case 'WALKING':     return makeCircleIcon(c);
    case 'SIGNAL_LOST': return makeXIcon();
    default:            return makeCircleIcon('#3a4460');
  }
}

// ── popup ─────────────────────────────────────────────────────────────────────

function fmtAge(age_s) {
  if (age_s === null || age_s === undefined) return '—';
  if (age_s < 60) return `${age_s}s fa`;
  return `${Math.floor(age_s / 60)}min fa`;
}

function degToCardinal(deg) {
  const dirs = ['N','NE','E','SE','S','SO','O','NO'];
  return dirs[Math.round(deg / 45) % 8];
}

const _STATE_COLOR = {
  AIRBORNE: 'var(--green)', SIGNAL_LOST: 'var(--red)', WALKING: 'var(--yellow)',
};

function buildPopup(p) {
  const icon     = STATE_ICON[p.state] || '❓';
  const stateClr = _STATE_COLOR[p.state] || 'var(--text)';
  const alt      = p.alt_m     != null ? `${Math.round(p.alt_m)}m AMSL`    : '—';
  const agl      = p.agl_m     != null ? `${Math.round(p.agl_m)}m AGL`     : '—';
  const spd      = p.speed_kmh != null ? `${Math.round(p.speed_kmh)} km/h` : '—';
  const vs       = p.vspeed_ms != null ? `${p.vspeed_ms > 0 ? '+' : ''}${p.vspeed_ms.toFixed(1)} m/s` : '—';
  const rotta    = (p.state === 'AIRBORNE' && p.course_deg != null)
    ? `<div class="popup-row">Rotta: <span>${Math.round(p.course_deg)}° ${degToCardinal(p.course_deg)}</span></div>`
    : '';
  const maps     = p.lat != null
    ? `<a class="popup-link" href="https://maps.google.com/?q=${p.lat},${p.lon}" target="_blank">📍 Google Maps</a>`
    : '';
  return `
    <div class="popup-name">${icon} ${p.name}</div>
    <div class="popup-row">Stato: <span style="color:${stateClr}">${p.state}</span></div>
    <div class="popup-row">Quota: <span>${alt} · ${agl}</span></div>
    <div class="popup-row">Speed: <span>${spd} · ${vs}</span></div>
    ${rotta}
    <div class="popup-row">Ultimo: <span>${fmtAge(p.age_s)}</span></div>
    ${maps}
  `;
}

// ── init map ──────────────────────────────────────────────────────────────────

const map = L.map('map', { zoomControl: false }).setView([46.0, 10.5], 8);

window.addEventListener('resize', () => setTimeout(() => map.invalidateSize(), 100));

const _osmLayer  = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a>',
  maxZoom: 19,
});
const _topoLayer = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
  attribution: 'Map data: © <a href="https://openstreetmap.org">OpenStreetMap</a> | Style: © <a href="https://opentopomap.org">OpenTopoMap</a>',
  maxZoom: 17,
});

_osmLayer.addTo(map);
L.control.layers({ 'OSM': _osmLayer, 'Topo': _topoLayer }, {}, { position: 'topright' }).addTo(map);

let markers      = {};
let tracks       = {};
let hasFitted    = false;
let refreshTimer = null;

// ── tracks ────────────────────────────────────────────────────────────────────

// The server decides what a track is (the whole current flight, cut by silence,
// and dropped once it is old): here we just draw whatever comes back, and clear
// the line when it comes back empty.
async function loadTrack(name, color, airborne) {
  try {
    const data = await fetch(`/api/pilots/${encodeURIComponent(name)}/track`).then(r => r.json());
    if (!data.length) { removeTrack(name); return; }
    const latlngs = data.map(p => [p.lat, p.lon]);
    const c = color || '#f5c542';
    // A finished flight stays on the map, thinner and paler than a live one:
    // still readable, but it never competes with who is flying now.
    const style = airborne
      ? { color: c, weight: 3, opacity: 0.75 }
      : { color: c, weight: 2, opacity: 0.35, dashArray: '4 5' };
    if (tracks[name]) {
      tracks[name].setLatLngs(latlngs);
      tracks[name].setStyle(style);
    } else {
      tracks[name] = L.polyline(latlngs, style).addTo(map);
    }
  } catch(e) {}
}

function removeTrack(name) {
  if (tracks[name]) { tracks[name].remove(); delete tracks[name]; }
}

// ── pilots ────────────────────────────────────────────────────────────────────

async function loadPilots(wlIds) {
  try {
    const url = (wlIds && wlIds.length > 0)
      ? `/api/pilots?wl=${wlIds.join(',')}`
      : '/api/pilots';
    const res  = await fetch(url);
    const data = await res.json();

    const incoming = new Set(data.map(p => p.name));
    for (const name of Object.keys(markers)) {
      if (!incoming.has(name)) {
        markers[name].remove();
        delete markers[name];
        removeTrack(name);
      }
    }

    const bounds = [];

    for (const p of data) {
      if (p.lat == null || p.lon == null) continue;

      const popup = buildPopup(p);
      const icon  = makeIcon(p.state, p.course_deg, p.color);

      if (markers[p.name]) {
        markers[p.name].setLatLng([p.lat, p.lon]).setIcon(icon);
        markers[p.name].getPopup().setContent(popup);
      } else {
        markers[p.name] = L.marker([p.lat, p.lon], { icon })
          .bindPopup(popup)
          .addTo(map);
      }
      bounds.push([p.lat, p.lon]);

      loadTrack(p.name, p.color, p.state === 'AIRBORNE');
    }

    if (bounds.length > 0 && !hasFitted) {
      map.fitBounds(bounds, { padding: [40, 40] });
      hasFitted = true;
    }

    updateSidebarList(data);
  } catch (e) {
    console.error('loadPilots error', e);
  }
}

function updateSidebarList(pilots) {
  const el = document.getElementById('pilot-list');
  if (!el) return;
  el.innerHTML = pilots.map(p => {
    const icon = STATE_ICON[p.state] || '❓';
    const cls  = (p.state || '').toLowerCase();
    const info = p.agl_m != null ? `${Math.round(p.agl_m)}m AGL` : '—';
    return `<div class="pilot-row ${cls}" onclick="focusPilot('${p.name}')">
      <span class="p-icon">${icon}</span>
      <span class="p-name">${p.name}</span>
      <span class="p-info">${info}</span>
    </div>`;
  }).join('');
}

window.focusPilot = function(name) {
  const m = markers[name];
  if (m) { map.setView(m.getLatLng(), 13); m.openPopup(); }
};

// ── watchlist filter ──────────────────────────────────────────────────────────

function getSelectedWlIds() {
  const boxes   = document.querySelectorAll('#wl-filter input[type=checkbox]');
  const all     = [...boxes];
  const checked = all.filter(c => c.checked).map(c => parseInt(c.value));
  return (checked.length === 0 || checked.length === all.length) ? [] : checked;
}

const filterDiv = document.getElementById('wl-filter');
if (filterDiv) {
  filterDiv.addEventListener('change', () => {
    clearInterval(refreshTimer);
    hasFitted = false;
    loadPilots(getSelectedWlIds());
    refreshTimer = setInterval(() => loadPilots(getSelectedWlIds()), 30000);
  });
}

loadPilots([]);
refreshTimer = setInterval(() => loadPilots(getSelectedWlIds()), 30000);
