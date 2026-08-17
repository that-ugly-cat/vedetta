'use strict';

// ── nav routing ───────────────────────────────────────────────────────────────

document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    item.classList.add('active');
    const sec = document.getElementById('section-' + item.dataset.section);
    if (sec) {
      sec.classList.add('active');
      onSectionEnter(item.dataset.section);
    }
  });
});

function onSectionEnter(name) {
  document.querySelector('.main').classList.toggle('map-active', name === 'live-map');
  if (name === 'my-devices')          loadMyDevices();
  if (name === 'my-watchlists')       loadMyWatchlists();
  if (name === 'my-profile')          loadMyProfile();
  if (name === 'admin-notifications') initAdminNotif();
  if (name === 'admin-watchlists')    loadWlSettings();
  if (name === 'admin-users')         loadUsers();
  if (name === 'admin-config')        loadConfig();
  if (name === 'live-map') {
    const nav = document.getElementById('main-nav');
    const tab = document.getElementById('nav-toggle');
    let delay = 0;
    if (nav && !nav.classList.contains('collapsed')) {
      nav.classList.add('collapsed');
      if (tab) tab.textContent = '›';
      delay = 270;
    }
    setTimeout(initDashMap, delay);
  }
}

// ── helpers ───────────────────────────────────────────────────────────────────

async function api(method, url, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(url, opts);
  if (!res.ok) {
    let msg = `${method} ${url} → ${res.status}`;
    try { const d = await res.json(); if (d.error) msg = d.error; } catch (_) {}
    throw new Error(msg);
  }
  return res.json();
}

function sourcesText(sources) {
  if (!sources || !Object.keys(sources).length) return '—';
  return Object.entries(sources).map(([k, v]) => `${k.toUpperCase()}:${v}`).join('  ');
}

function badgeRole(role) {
  return role === 'admin'
    ? `<span class="badge badge-yellow">admin</span>`
    : `<span class="badge badge-gray">pilot</span>`;
}

function deviceChips(devs) {
  if (!devs || !devs.length) return '<span class="muted">—</span>';
  return devs.map(d =>
    `<span style="font-family:monospace;font-size:11px;background:var(--surface2);
      padding:2px 6px;border-radius:4px;margin-right:4px;">${d.display_name}</span>`
  ).join('');
}

// ── map popup (shared with map.js) ───────────────────────────────────────────

const _STATE_ICON = {
  AIRBORNE: '✈️', GROUNDED: '🛬', WALKING: '🚶', SIGNAL_LOST: '📵', UNKNOWN: '❓',
};

function fmtAge(age_s) {
  if (age_s === null || age_s === undefined) return '—';
  if (age_s < 60) return T.js_age_s.replace('{n}', age_s);
  return T.js_age_min.replace('{n}', Math.floor(age_s / 60));
}

function degToCardinal(deg) {
  return T.js_dirs[Math.round(deg / 45) % 8];
}

const _STATE_COLOR = {
  AIRBORNE: 'var(--green)', SIGNAL_LOST: 'var(--red)', WALKING: 'var(--yellow)',
};

function buildPopup(p) {
  const icon      = _STATE_ICON[p.state] || '❓';
  const stateClr  = _STATE_COLOR[p.state] || 'var(--text)';
  const alt       = p.alt_m     != null ? `${Math.round(p.alt_m)}m AMSL`    : '—';
  const agl       = p.agl_m     != null ? `${Math.round(p.agl_m)}m AGL`     : '—';
  const spd       = p.speed_kmh != null ? `${Math.round(p.speed_kmh)} km/h` : '—';
  const vs        = p.vspeed_ms != null ? `${p.vspeed_ms > 0 ? '+' : ''}${p.vspeed_ms.toFixed(1)} m/s` : '—';
  const rotta     = (p.state === 'AIRBORNE' && p.course_deg != null)
    ? `<div class="popup-row">${T.js_popup_route} <span>${Math.round(p.course_deg)}° ${degToCardinal(p.course_deg)}</span></div>`
    : '';
  const maps      = p.lat != null
    ? `<a class="popup-link" href="https://maps.google.com/?q=${p.lat},${p.lon}" target="_blank">📍 Google Maps</a>`
    : '';
  return `
    <div class="popup-name">${icon} ${p.name}</div>
    <div class="popup-row">${T.js_popup_state} <span style="color:${stateClr}">${p.state}</span></div>
    <div class="popup-row">${T.js_popup_alt} <span>${alt} · ${agl}</span></div>
    <div class="popup-row">${T.js_popup_speed} <span>${spd} · ${vs}</span></div>
    ${rotta}
    <div class="popup-row">${T.js_popup_last} <span>${fmtAge(p.age_s)}</span></div>
    ${maps}
  `;
}

// ── My Devices ────────────────────────────────────────────────────────────────

const SOURCE_KEYS = ['fanet', 'flarm', 'ogntracker', 'naviter', 'icao', 'puretrack', 'grappasafe'];

function readDeviceForm() {
  const sources = {};
  SOURCE_KEYS.forEach(k => {
    const v = document.getElementById('src-' + k).value.trim();
    if (v) sources[k] = v;
  });
  return {
    display_name: document.getElementById('device-name').value.trim(),
    sources,
    color: document.getElementById('device-color').value,
  };
}

function fillDeviceForm(dev) {
  document.getElementById('device-name').value = dev.display_name;
  SOURCE_KEYS.forEach(k => {
    document.getElementById('src-' + k).value = dev.sources[k] || '';
  });
  document.getElementById('device-color').value = dev.color || '#4a9eff';
  document.getElementById('device-edit-id').value = dev.id;
  document.getElementById('device-form-title').textContent = T.js_edit_device;
  document.getElementById('device-cancel').style.display = '';
}

function resetDeviceForm() {
  document.getElementById('device-form').reset();
  document.getElementById('device-color').value = '#4a9eff';
  document.getElementById('device-edit-id').value = '';
  document.getElementById('device-form-title').textContent = T.js_add_device;
  document.getElementById('device-cancel').style.display = 'none';
}

async function loadMyDevices() {
  const tbody = document.getElementById('my-devices-body');
  try {
    const devices = await api('GET', '/api/me/devices');
    tbody.innerHTML = devices.length ? devices.map(d => {
      const swatch = `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;
        background:${d.color || '#4a9eff'};margin-right:6px;border:1px solid rgba(255,255,255,0.2);"></span>`;
      return `<tr>
        <td><strong>${swatch}${d.display_name}</strong></td>
        <td class="muted" style="font-family:monospace;font-size:12px;">${sourcesText(d.sources)}</td>
        <td><div class="actions">
          <button class="btn btn-ghost btn-sm" onclick="editDevice(${d.id})">✏️</button>
          <button class="btn btn-danger  btn-sm" onclick="deleteDevice(${d.id})">🗑️</button>
        </div></td>
      </tr>`;
    }).join('')
    : `<tr><td colspan="3" class="muted">${T.js_no_devices}</td></tr>`;
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="3" class="muted">${T.js_error_loading}</td></tr>`;
  }
}

window.editDevice = async function(id) {
  const devices = await api('GET', '/api/me/devices');
  const dev = devices.find(d => d.id === id);
  if (dev) fillDeviceForm(dev);
};

window.deleteDevice = async function(id) {
  if (!confirm(T.js_confirm_del_device)) return;
  await api('DELETE', `/api/me/devices/${id}`);
  loadMyDevices();
};

document.getElementById('device-form').addEventListener('submit', async e => {
  e.preventDefault();
  const data = readDeviceForm();
  if (!data.display_name) return;
  const editId = document.getElementById('device-edit-id').value;
  if (editId) {
    await api('PUT', `/api/me/devices/${editId}`, data);
  } else {
    await api('POST', '/api/me/devices', data);
  }
  resetDeviceForm();
  loadMyDevices();
});

document.getElementById('device-cancel').addEventListener('click', resetDeviceForm);

// The ingest token is minted by the server, never typed by hand: it is the only
// thing standing between a stranger and this pilot's position on the map.
document.getElementById('src-grappasafe-gen')?.addEventListener('click', async () => {
  try {
    const res = await api('GET', '/api/me/ingest-token');
    document.getElementById('src-grappasafe').value = res.token;
  } catch (e) {
    alert(T.js_token_error);
  }
});

// ── My Watchlists (self-service join / leave) ─────────────────────────────────

async function loadMyWatchlists() {
  const container = document.getElementById('my-watchlists-container');
  container.innerHTML = `<p class="muted">${T.js_loading}</p>`;
  try {
    const [myWls, allWls] = await Promise.all([
      api('GET', '/api/me/watchlists'),
      api('GET', '/api/watchlists'),
    ]);
    const myIds = new Set(myWls.map(w => w.id));

    if (!allWls.length) {
      container.innerHTML = `<p class="muted">${T.js_no_watchlists}</p>`;
      return;
    }

    container.innerHTML = allWls.map(wl => {
      const member = myIds.has(wl.id);
      return `<div class="card" style="display:flex;align-items:center;gap:16px;">
        <div style="flex:1">
          <div style="font-weight:600;">${wl.name}</div>
          ${member ? `<span class="badge badge-green" style="margin-top:4px;">${T.js_member_badge}</span>` : ''}
        </div>
        <div class="flex gap-8">
          ${member
            ? `<button class="btn btn-ghost btn-sm" onclick="openMapFor(${wl.id})">${T.js_btn_map}</button>
               <button class="btn btn-danger btn-sm" onclick="leaveWl(${wl.id})">${T.js_btn_leave}</button>`
            : `<button class="btn btn-primary btn-sm" onclick="joinWl(${wl.id})">${T.js_btn_join}</button>`
          }
        </div>
      </div>`;
    }).join('');
  } catch(e) {
    container.innerHTML = `<p class="muted">${T.js_error_loading}</p>`;
  }
}

window.joinWl = async function(wlId) {
  await api('POST', `/api/watchlists/${wlId}/join`);
  loadMyWatchlists();
};

window.leaveWl = async function(wlId) {
  if (!confirm(T.js_confirm_leave_wl)) return;
  await api('DELETE', `/api/watchlists/${wlId}/leave`);
  loadMyWatchlists();
};

// ── Live Map (dashboard) ──────────────────────────────────────────────────────

let dashMap      = null;
let dashMarkers  = {};
let dashTracks   = {};
let dashTimer    = null;
let dashHasFitted = false;

function _currentWlId() {
  return document.getElementById('dash-wl-select')?.value || null;
}

window.addEventListener('resize', () => {
  if (dashMap) setTimeout(() => dashMap.invalidateSize(), 100);
});

function initDashMap() {
  if (!dashMap) {
    dashMap = L.map('dash-map', { zoomControl: false }).setView([46.0, 10.5], 8);
    const _osmLayer  = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a>',
      maxZoom: 19,
    });
    const _topoLayer = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
      attribution: 'Map data: © <a href="https://openstreetmap.org">OpenStreetMap</a> | Style: © <a href="https://opentopomap.org">OpenTopoMap</a>',
      maxZoom: 17,
    });
    _osmLayer.addTo(dashMap);
    L.control.layers({ 'OSM': _osmLayer, 'Topo': _topoLayer }, {}, { position: 'topright' }).addTo(dashMap);
  }
  setTimeout(() => dashMap.invalidateSize(), 100);
  setTimeout(() => dashMap.invalidateSize(), 450);
  clearInterval(dashTimer);
  dashHasFitted = false;
  loadDashPilots(_currentWlId());
  dashTimer = setInterval(() => loadDashPilots(_currentWlId()), 30000);
}

function _dashArrow(deg, color) {
  return L.divIcon({
    html: `<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 30 30">
      <g transform="rotate(${deg || 0}, 15, 15)">
        <polygon points="15,3 25,25 15,19 5,25"
                 fill="${color || '#f5c542'}" stroke="white" stroke-width="2" stroke-linejoin="round"/>
      </g></svg>`,
    className: '', iconSize: [30,30], iconAnchor: [15,15], popupAnchor: [0,-18],
  });
}

function _dashCircle(color) {
  return L.divIcon({
    html: `<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 22 22">
      <circle cx="11" cy="11" r="8" fill="${color}" stroke="white" stroke-width="2.5"/></svg>`,
    className: '', iconSize: [22,22], iconAnchor: [11,11], popupAnchor: [0,-14],
  });
}

function _dashX() {
  return L.divIcon({
    html: `<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 22 22">
      <circle cx="11" cy="11" r="9" fill="#ff5c5c" stroke="white" stroke-width="2"/>
      <line x1="6" y1="6" x2="16" y2="16" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
      <line x1="16" y1="6" x2="6" y2="16" stroke="white" stroke-width="2.5" stroke-linecap="round"/></svg>`,
    className: '', iconSize: [22,22], iconAnchor: [11,11], popupAnchor: [0,-14],
  });
}

function dashIcon(state, course_deg, color) {
  const c = color || '#4a9eff';
  switch(state) {
    case 'AIRBORNE':    return _dashArrow(course_deg, c);
    case 'GROUNDED':    return _dashCircle(c);
    case 'WALKING':     return _dashCircle(c);
    case 'SIGNAL_LOST': return _dashX();
    default:            return _dashCircle('#3a4460');
  }
}

async function loadDashTrack(name, color, airborne) {
  if (!dashMap) return;
  try {
    const data = await fetch(`/api/pilots/${encodeURIComponent(name)}/track`).then(r => r.json());
    if (!data.length) { removeDashTrack(name); return; }
    const latlngs = data.map(p => [p.lat, p.lon]);
    const c = color || '#f5c542';
    const style = airborne
      ? { color: c, weight: 3, opacity: 0.75 }
      : { color: c, weight: 2, opacity: 0.35, dashArray: '4 5' };
    if (dashTracks[name]) {
      dashTracks[name].setLatLngs(latlngs);
      dashTracks[name].setStyle(style);
    } else {
      dashTracks[name] = L.polyline(latlngs, style).addTo(dashMap);
    }
  } catch(e) {}
}

function removeDashTrack(name) {
  if (dashTracks[name]) { dashTracks[name].remove(); delete dashTracks[name]; }
}

async function loadDashPilots(wlId) {
  if (!dashMap) return;
  const url  = wlId ? `/api/watchlist/${wlId}/pilots` : '/api/pilots';
  const data = await fetch(url).then(r => r.json());
  const incoming = new Set(data.map(p => p.name));
  for (const k of Object.keys(dashMarkers)) {
    if (!incoming.has(k)) {
      dashMarkers[k].remove(); delete dashMarkers[k];
      removeDashTrack(k);
    }
  }
  const bounds = [];
  for (const p of data) {
    if (p.lat == null) continue;
    const icon  = dashIcon(p.state, p.course_deg, p.color);
    const popup = buildPopup(p);
    if (dashMarkers[p.name]) {
      dashMarkers[p.name].setLatLng([p.lat, p.lon]).setIcon(icon);
      dashMarkers[p.name].getPopup().setContent(popup);
    } else {
      dashMarkers[p.name] = L.marker([p.lat, p.lon], { icon })
        .bindPopup(popup).addTo(dashMap);
    }
    bounds.push([p.lat, p.lon]);
    loadDashTrack(p.name, p.color, p.state === 'AIRBORNE');
  }
  if (bounds.length && !dashHasFitted) {
    dashMap.fitBounds(bounds, { padding: [40,40] });
    dashHasFitted = true;
  }
}

document.getElementById('dash-wl-select')?.addEventListener('change', () => {
  clearInterval(dashTimer);
  dashHasFitted = false;
  const wlId = _currentWlId();
  loadDashPilots(wlId);
  dashTimer = setInterval(() => loadDashPilots(_currentWlId()), 30000);
});

window.openMapFor = function(wlId) {
  document.querySelector('[data-section="live-map"]').click();
  const sel = document.getElementById('dash-wl-select');
  if (sel) { sel.value = wlId; sel.dispatchEvent(new Event('change')); }
};

// ── Admin: Pilots ─────────────────────────────────────────────────────────────

let allUsers = [];

window.removeWlMember = async function(wlId, uid) {
  if (!confirm(T.js_confirm_remove_member)) return;
  await api('DELETE', `/api/admin/watchlists/${wlId}/members/${uid}`);
  loadWlSettings();
};

window.addWlMember = async function(wlId) {
  const uid = document.getElementById(`user-pick-${wlId}`).value;
  if (!uid) return;
  await api('POST', `/api/admin/watchlists/${wlId}/members`, { user_id: parseInt(uid) });
  loadWlSettings();
};

// ── Admin: Notifications ──────────────────────────────────────────────────────

const EVENT_LABELS = {
  takeoff:         T.js_ev_takeoff,
  landing:         T.js_ev_landing,
  bad_air:         T.js_ev_bad_air,
  bad_landing:     T.js_ev_bad_landing,
  reserve:         T.js_ev_reserve,
  impact:          T.js_ev_impact,
  climbing_well:   T.js_ev_climbing,
  in_orbita:       T.js_ev_orbita,
  piange_giallo:   T.js_ev_piange,
  ha_fatto_strada: T.js_ev_strada,
  signal_lost:     T.js_ev_signal_lost,
  signal_found:    T.js_ev_signal_found,
};

// ── Admin: thresholds ─────────────────────────────────────────────────────────
// Every number the state machine and the two safety nets work with. They used
// to be environment variables: changing one meant rebuilding the image.

const CONFIG_CATEGORIES = ['volo', 'eventi', 'riserva', 'impatto', 'sistema', 'tracce', 'milestone'];

async function loadConfig() {
  const wrap = document.getElementById('config-groups');
  let rows;
  try {
    rows = await api('GET', '/api/admin/config');
  } catch (e) {
    wrap.innerHTML = `<p class="muted">${T.js_error_loading}</p>`;
    return;
  }
  const groups = {};
  rows.forEach(r => (groups[r.categoria] = groups[r.categoria] || []).push(r));
  const order = CONFIG_CATEGORIES.filter(c => groups[c])
    .concat(Object.keys(groups).filter(c => !CONFIG_CATEGORIES.includes(c)));

  wrap.innerHTML = order.map(cat => `
    <div class="config-group">
      <div class="config-group-title">${T['js_cfg_' + cat] || cat}</div>
      ${groups[cat].map(r => `
        <div class="config-row">
          <div class="config-desc">
            <div>${r.descrizione}</div>
            <div class="muted" style="font-size:11px;font-family:monospace;">${r.key}</div>
          </div>
          <input class="input config-input" type="number" step="any"
                 id="cfg-${r.key}" value="${r.value}"
                 onchange="saveConfig('${r.key}', this)">
        </div>`).join('')}
    </div>`).join('');
}

window.saveConfig = async function(key, input) {
  const value = parseFloat(input.value);
  if (Number.isNaN(value)) {
    input.classList.add('config-error');
    return;
  }
  try {
    await api('PUT', `/api/admin/config/${key}`, { value });
    input.classList.remove('config-error');
    input.classList.add('config-saved');
    setTimeout(() => input.classList.remove('config-saved'), 1200);
  } catch (e) {
    input.classList.add('config-error');
  }
};

async function initAdminNotif() {
  const sel = document.getElementById('admin-wl-notif');
  await populateWlSelect(sel);
  sel.addEventListener('change', () => loadNotifPrefs(sel.value));
}

async function loadNotifPrefs(wlId) {
  const card = document.getElementById('notif-card');
  if (!wlId) { card.classList.add('hidden'); return; }
  card.classList.remove('hidden');
  const prefs = await api('GET', `/api/admin/watchlists/${wlId}/notifications`);
  const grid  = document.getElementById('notif-grid');
  grid.innerHTML = prefs.map(p => {
    const label    = EVENT_LABELS[p.event_key] || p.event_key;
    const disabled = p.always_on ? 'disabled' : '';
    const checked  = p.enabled   ? 'checked'  : '';
    return `<div class="notif-item${p.always_on ? ' always-on' : ''}">
      <div>
        <div class="notif-label">${label}</div>
        ${p.always_on ? `<div class="notif-always">${T.js_always_on}</div>` : ''}
      </div>
      <label class="toggle">
        <input type="checkbox" ${checked} ${disabled}
          onchange="setNotif(${wlId},'${p.event_key}',this.checked)">
        <span class="toggle-slider"></span>
      </label>
    </div>`;
  }).join('');
}

window.setNotif = async function(wlId, eventKey, enabled) {
  await api('PUT', `/api/admin/watchlists/${wlId}/notifications/${eventKey}`, { enabled });
};

// ── Admin: Watchlist Settings ─────────────────────────────────────────────────

async function loadWlSettings() {
  const [watchlists, users] = await Promise.all([
    api('GET', '/api/admin/watchlists'),
    api('GET', '/api/admin/users'),
  ]);
  const container = document.getElementById('wl-settings-list');

  if (!watchlists.length) {
    container.innerHTML = '';
    return;
  }

  const perWl = await Promise.all(
    watchlists.map(wl => Promise.all([
      api('GET', `/api/admin/watchlists/${wl.id}/members`),
      api('GET', `/api/admin/watchlists/${wl.id}/devices`),
    ]))
  );

  const userOpts = `<option value="">${T.js_user_pick_ph}</option>` +
    users.map(u => `<option value="${u.id}">${u.username}</option>`).join('');

  container.innerHTML = watchlists.map((wl, i) => {
    const [members, devices] = perWl[i];
    const byOwner = {};
    devices.forEach(d => { (byOwner[d.owner] = byOwner[d.owner] || []).push(d); });

    const rows = members.length
      ? members.map(m => `<tr>
          <td><strong>${m.username}</strong></td>
          <td>${deviceChips(byOwner[m.username] || [])}</td>
          <td>${badgeRole(m.watchlist_role)}</td>
          <td><button class="btn btn-danger btn-sm" onclick="removeWlMember(${wl.id},${m.id})">✕</button></td>
        </tr>`).join('')
      : `<tr><td colspan="4" class="muted">${T.js_no_pilots}</td></tr>`;

    return `
    <div class="card">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
        <div class="card-title" style="margin:0;">${wl.name}</div>
        <button class="btn btn-danger btn-sm" onclick="deleteWatchlist(${wl.id},'${wl.name.replace(/'/g,"\\'")}')">
          ${T.js_btn_delete_wl}
        </button>
      </div>

      <div class="device-form" style="margin-bottom:20px;">
        <div class="flex gap-8">
          <div style="flex:1">
            <label class="field-label">${T.js_wl_telegram_label}</label>
            <input class="input" id="chat-${wl.id}" value="${wl.telegram_chat_id || ''}" placeholder="-100123456789" style="margin:0;">
          </div>
          <div>
            <label class="field-label">${T.js_wl_lang_label}</label>
            <select class="select" id="lang-${wl.id}" style="margin:0;">
              <option value="en" ${wl.language==='en'?'selected':''}>${T.js_wl_lang_en}</option>
              <option value="it" ${wl.language==='it'?'selected':''}>${T.js_wl_lang_it}</option>
            </select>
          </div>
        </div>
        <button class="btn btn-ghost btn-sm" style="width:auto;margin-top:8px;" onclick="saveWlSettings(${wl.id})">
          ${T.js_btn_save_settings}
        </button>
      </div>

      <div class="field-label" style="margin-bottom:8px;">${T.js_label_pilots}</div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>${T.js_th_pilot}</th><th>${T.js_th_device}</th><th>${T.js_th_role}</th><th></th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <div class="mt-16 flex gap-8">
        <select class="select" id="user-pick-${wl.id}" style="max-width:240px;margin:0;">${userOpts}</select>
        <button class="btn btn-ghost btn-sm" onclick="addWlMember(${wl.id})">${T.js_btn_add_pilot}</button>
      </div>
    </div>`;
  }).join('');
}

window.deleteWatchlist = async function(wlId, name) {
  if (!confirm(T.js_confirm_del_wl.replace('{name}', name))) return;
  await api('DELETE', `/api/admin/watchlists/${wlId}`);
  loadWlSettings();
};

window.saveWlSettings = async function(wlId) {
  const chat_id  = document.getElementById(`chat-${wlId}`).value.trim();
  const language = document.getElementById(`lang-${wlId}`).value;
  await api('PUT', `/api/admin/watchlists/${wlId}/settings`, { telegram_chat_id: chat_id || null, language });
};

document.getElementById('new-wl-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  const name    = document.getElementById('new-wl-name').value.trim();
  const chat_id = document.getElementById('new-wl-chat-id').value.trim();
  const lang    = document.getElementById('new-wl-lang').value;
  if (!name) return;
  await api('POST', '/api/admin/watchlists', { name, telegram_chat_id: chat_id || null, language: lang });
  e.target.reset();
  loadWlSettings();
});

// ── My Profile ────────────────────────────────────────────────────────────────

async function loadMyProfile() {
  const u = await api('GET', '/api/me');
  document.getElementById('my-username').textContent     = u.username || '—';
  document.getElementById('my-first-name').value         = u.first_name || '';
  document.getElementById('my-last-name').value          = u.last_name  || '';
  document.getElementById('my-email').value              = u.email      || '';
  document.getElementById('my-emergency-phone').value    = u.emergency_phone || '';
}

document.getElementById('my-profile-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  try {
    await api('PUT', '/api/me/profile', {
      first_name:      document.getElementById('my-first-name').value.trim(),
      last_name:       document.getElementById('my-last-name').value.trim(),
      email:           document.getElementById('my-email').value.trim(),
      emergency_phone: document.getElementById('my-emergency-phone').value.trim(),
    });
    alert(T.js_profile_updated);
  } catch (err) { alert(err.message || T.js_error_generic); }
});

document.getElementById('my-password-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  const newPwd  = document.getElementById('my-new-pwd').value;
  const newPwd2 = document.getElementById('my-new-pwd2').value;
  if (newPwd !== newPwd2) { alert(T.js_pwd_mismatch); return; }
  try {
    await api('PUT', '/api/me/password', {
      current_password: document.getElementById('my-current-pwd').value,
      new_password:     newPwd,
    });
    alert(T.js_pwd_updated);
    e.target.reset();
  } catch (err) { alert(err.message || T.js_error_generic); }
});

// ── Admin: Users ──────────────────────────────────────────────────────────────

async function loadUsers() {
  const users = await api('GET', '/api/admin/users');
  document.getElementById('admin-users-body').innerHTML = users.map(u => {
    const nome = [u.first_name, u.last_name].filter(Boolean).join(' ') || '<span class="muted">—</span>';
    const enc  = encodeURIComponent(JSON.stringify({
      first_name: u.first_name || '', last_name: u.last_name || '',
      email: u.email || '', emergency_phone: u.emergency_phone || '', role: u.role,
    }));
    return `<tr>
      <td><strong>${u.username}</strong></td>
      <td>${nome}</td>
      <td>${badgeRole(u.role)}</td>
      <td class="flex gap-8">
        <button class="btn btn-ghost btn-sm" onclick="editUser(${u.id},'${u.username}',decodeURIComponent('${enc}'))">✏️</button>
        <button class="btn btn-ghost btn-sm" onclick="promptResetPwd(${u.id},'${u.username}')">🔑</button>
        <button class="btn btn-danger btn-sm" onclick="deleteUser(${u.id},'${u.username}')">✕</button>
      </td>
    </tr>`;
  }).join('');
}

window.editUser = function(uid, username, dataJson) {
  const d = JSON.parse(dataJson);
  document.getElementById('edit-user-id').value       = uid;
  document.getElementById('edit-user-label').textContent = username;
  document.getElementById('edit-first-name').value    = d.first_name;
  document.getElementById('edit-last-name').value     = d.last_name;
  document.getElementById('edit-email').value         = d.email;
  document.getElementById('edit-emergency-phone').value = d.emergency_phone;
  document.getElementById('edit-role').value          = d.role;
  document.getElementById('edit-user-card').classList.remove('hidden');
  document.getElementById('edit-user-card').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
};

window.cancelEditUser = function() {
  document.getElementById('edit-user-card').classList.add('hidden');
};

document.getElementById('edit-user-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  const uid = parseInt(document.getElementById('edit-user-id').value);
  await api('PUT', `/api/admin/users/${uid}/profile`, {
    first_name:      document.getElementById('edit-first-name').value.trim(),
    last_name:       document.getElementById('edit-last-name').value.trim(),
    email:           document.getElementById('edit-email').value.trim(),
    emergency_phone: document.getElementById('edit-emergency-phone').value.trim(),
    role:            document.getElementById('edit-role').value,
  });
  document.getElementById('edit-user-card').classList.add('hidden');
  loadUsers();
});

window.promptResetPwd = async function(uid, username) {
  const pwd = prompt(T.js_pwd_reset_prompt.replace('{username}', username));
  if (!pwd || pwd.length < 6) { alert(T.js_pwd_too_short); return; }
  await api('PUT', `/api/admin/users/${uid}/password`, { password: pwd });
  alert(T.js_pwd_updated);
};

window.deleteUser = async function(uid, username) {
  if (!confirm(T.js_confirm_del_user.replace('{username}', username))) return;
  try {
    await api('DELETE', `/api/admin/users/${uid}`);
    loadUsers();
  } catch (e) {
    alert(e.message || T.js_error_del_user);
  }
};

document.getElementById('new-user-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  const username = document.getElementById('new-username').value.trim();
  const password = document.getElementById('new-password').value;
  const role     = document.getElementById('new-role').value;
  if (!username || !password) return;
  await api('POST', '/api/admin/users', { username, password, role });
  e.target.reset();
  loadUsers();
});

// ── shared: populate watchlist selects ───────────────────────────────────────

async function populateWlSelect(el) {
  const watchlists = await api('GET', '/api/admin/watchlists');
  el.innerHTML = `<option value="">${T.js_sel_wl_ph}</option>` +
    watchlists.map(w => `<option value="${w.id}">${w.name}</option>`).join('');
}

// ── help modal ────────────────────────────────────────────────────────────────

function _renderMd(md) {
  const lines = md.split('\n');
  let html = '', i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith('### ')) {
      html += `<h3>${_inlineMd(line.slice(4))}</h3>`; i++;
    } else if (line.startsWith('## ')) {
      html += `<h2>${_inlineMd(line.slice(3))}</h2>`; i++;
    } else if (line.startsWith('- ')) {
      html += '<ul>';
      while (i < lines.length && lines[i].startsWith('- ')) {
        html += `<li>${_inlineMd(lines[i].slice(2))}</li>`; i++;
      }
      html += '</ul>';
    } else if (line.startsWith('> ')) {
      html += `<blockquote>${_inlineMd(line.slice(2))}</blockquote>`; i++;
    } else if (line.trim() === '') {
      i++;
    } else {
      let para = '';
      while (i < lines.length && lines[i].trim() !== '' &&
             !lines[i].startsWith('## ') && !lines[i].startsWith('### ') &&
             !lines[i].startsWith('- ') && !lines[i].startsWith('> ')) {
        para += (para ? ' ' : '') + lines[i].trim(); i++;
      }
      html += `<p>${_inlineMd(para)}</p>`;
    }
  }
  return html;
}

function _inlineMd(text) {
  return text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/\*(.+?)\*/g,'<em>$1</em>')
    .replace(/`(.+?)`/g,'<code>$1</code>')
    .replace(/\[(.+?)\]\((https?:\/\/[^)]+)\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>');
}

window.openHelp = async function(doc, title) {
  const overlay = document.getElementById('help-modal');
  const body    = document.getElementById('help-modal-body');
  document.getElementById('help-modal-title').textContent = title || T.help_title;
  body.innerHTML = `<p class="muted">${T.js_help_loading}</p>`;
  overlay.style.display = 'flex';
  try {
    const md = await fetch(`/static/docs/${window.LANG}/${doc}.md`, { cache: 'no-store' }).then(r => r.text());
    body.innerHTML = _renderMd(md);
  } catch(e) {
    body.innerHTML = `<p class="muted">${T.js_help_error}</p>`;
  }
};

window.closeHelp = function() {
  document.getElementById('help-modal').style.display = 'none';
};

// ── init ──────────────────────────────────────────────────────────────────────

loadMyDevices();
