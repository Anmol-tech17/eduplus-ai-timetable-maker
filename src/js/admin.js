/**
 * admin.js — EduPlus Admin Dashboard Logic
 * All scheduling, generation, and publishing actions are SIMULATED (mock only).
 * No real CP-SAT solver, database, or backend is connected.
 */
(function () {
  "use strict";

// ─── AUTH GUARD ───────────────────────────────────────────────────────────────
const _adminUser = (() => {
  try {
    const u = JSON.parse(sessionStorage.getItem('eduplus_user') || 'null');
    if (!u || u.role !== 'admin') { window.location.href = 'index.html'; return null; }
    return u;
  } catch (_) { window.location.href = 'index.html'; return null; }
})();
if (_adminUser) {
  document.getElementById('sidebar-username').textContent = _adminUser.name;
  document.getElementById('sidebar-avatar').textContent =
    _adminUser.name.split(' ').map(p => p[0]).join('').slice(0,2).toUpperCase();
}

// ─── DATA ALIASES ─────────────────────────────────────────────────────────────
const D = window.EduPlusData;
const { TEACHERS, ROOMS, SUBJECTS, ENROLLMENT_GROUPS,
        MOCK_TIMETABLE_VALID, MOCK_TIMETABLE_CONFLICT,
        DEMO_REQUESTS, TIME_SLOTS, DAYS, LUNCH_POLICY, SUMMARY_STATS } = D;

// ─── PANEL NAVIGATION ─────────────────────────────────────────────────────────
const PANEL_TITLES = {
  'overview':  'Dashboard',
  'timetable': 'Timetable Grid',
  'generate':  'Generate & Validate',
  'conflicts': 'Conflict Report',
  'teachers':  'Teachers',
  'rooms':     'Rooms & Labs',
  'requests':  'Request Inbox',
};

function showPanel(name) {
  document.querySelectorAll('.panel').forEach(p => {
    p.classList.add('hidden'); p.classList.remove('active');
  });
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const panel = document.getElementById(`panel-${name}`);
  const navEl  = document.getElementById(`nav-${name}`);
  if (panel) { panel.classList.remove('hidden'); panel.classList.add('active'); }
  if (navEl)   navEl.classList.add('active');
  document.getElementById('topbar-title').textContent = PANEL_TITLES[name] || name;
  // Lazy-render panels
  if (name === 'timetable') renderTimetableGrid(MOCK_TIMETABLE_VALID, null);
  if (name === 'conflicts')  renderConflictPanel();
  if (name === 'teachers')   renderTeachers();
  if (name === 'rooms')      renderRooms();
  if (name === 'requests')   renderRequests();
  if (name === 'generate')   renderGeneratePanel();
}

// ─── SIGN OUT ─────────────────────────────────────────────────────────────────
function signOut() {
  sessionStorage.removeItem('eduplus_user');
  window.location.href = 'index.html';
}

// ─── TOAST ───────────────────────────────────────────────────────────────────
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.setAttribute('role', 'alert');
  const icons = { success: '✓', error: '✕', info: 'ℹ', warning: '⚠' };
  toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${message}</span>`;
  container.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add('show'));
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 350);
  }, 4000);
}

// ─── MODAL ────────────────────────────────────────────────────────────────────
function openModal(title, bodyHTML) {
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-body').innerHTML = bodyHTML;
  document.getElementById('session-modal').classList.add('open');
}
function closeModal(id) {
  document.getElementById(id).classList.remove('open');
}

// ─── TIMETABLE GRID RENDERER ─────────────────────────────────────────────────
let _currentFilterTeacher = '';
let _currentFilterRoom    = '';

function buildSubjectMap() {
  const m = {};
  SUBJECTS.forEach(s => { m[s.id] = s; });
  return m;
}
function buildTeacherMap() {
  const m = {};
  TEACHERS.forEach(t => { m[t.id] = t; });
  return m;
}
function buildRoomMap() {
  const m = {};
  ROOMS.forEach(r => { m[r.id] = r; });
  return m;
}
const SUBJECT_MAP = buildSubjectMap();
const TEACHER_MAP = buildTeacherMap();
const ROOM_MAP    = buildRoomMap();

const LUNCH_SLOT = 'TS6'; // DIV_3A lunch

function sessionCSSClass(type, targetGroup) {
  if (type === 'practical') return 'session-practical';
  if (type === 'tutorial')  return 'session-tutorial';
  if (targetGroup && (targetGroup.startsWith('EG_') || SUBJECTS.find(s => s.elective && s.id === 'SUB305' || s.id === 'SUB306' || s.id === 'SUB307'))) {
    const electiveTargets = ['EG_CV','EG_NLP','EG_ROBO'];
    if (electiveTargets.some(e => targetGroup === e)) return 'session-elective';
  }
  return 'session-lecture';
}

function renderTimetableGrid(timetable, filterOpts) {
  const grid = document.getElementById('tt-grid');
  if (!grid) return;

  // Populate filter dropdowns once
  if (!document.getElementById('filter-teacher').options.length > 1) {
    const teacherSel = document.getElementById('filter-teacher');
    TEACHERS.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.id; opt.textContent = t.shortName;
      teacherSel.appendChild(opt);
    });
    const roomSel = document.getElementById('filter-room');
    ROOMS.forEach(r => {
      const opt = document.createElement('option');
      opt.value = r.id; opt.textContent = r.name;
      roomSel.appendChild(opt);
    });
  }

  const ft = _currentFilterTeacher;
  const fr = _currentFilterRoom;

  // Determine if filter notice should show
  const filterNotice = document.getElementById('filter-notice');
  if (ft || fr) {
    filterNotice.classList.remove('hidden');
    const tName = ft ? (TEACHER_MAP[ft]?.shortName || ft) : '';
    const rName = fr ? (ROOM_MAP[fr]?.name || fr) : '';
    document.getElementById('filter-notice-text').textContent =
      `Filtered: ${tName ? `Teacher: ${tName}` : ''} ${rName ? `Room: ${rName}` : ''}. Non-matching slots appear empty.`;
  } else {
    filterNotice.classList.add('hidden');
  }

  // Build session map: day → slot → [sessions]
  const sessionMap = {};
  DAYS.forEach(day => { sessionMap[day] = {}; TIME_SLOTS.forEach(ts => { sessionMap[day][ts.id] = []; }); });

  const filtered = timetable.sessions.filter(s => {
    if (s.hidden) return false;
    if (ft && s.teacherId !== ft) return false;
    if (fr && s.roomId !== fr) return false;
    return true;
  });
  filtered.forEach(s => {
    if (sessionMap[s.day] && sessionMap[s.day][s.slot] !== undefined) {
      sessionMap[s.day][s.slot].push(s);
    }
  });

  // Is this the conflict timetable?
  const isConflict = timetable.status === 'diagnostic';

  // Build HTML
  let html = '';
  // Header row
  html += `<div class="tt-header-cell" role="columnheader">Time</div>`;
  DAYS.forEach(d => { html += `<div class="tt-header-cell" role="columnheader">${d}</div>`; });

  TIME_SLOTS.forEach(ts => {
    const isLunch = ts.id === LUNCH_SLOT;
    // Time cell
    html += `<div class="tt-time-cell" role="rowheader" aria-label="${ts.label}">${ts.label}</div>`;
    DAYS.forEach(day => {
      const slotSessions = sessionMap[day][ts.id] || [];
      if (isLunch) {
        html += `<div class="tt-cell lunch-cell" role="cell" aria-label="Lunch break"><div class="tt-lunch-label">🍽 Lunch</div></div>`;
        return;
      }
      if (slotSessions.length === 0) {
        html += `<div class="tt-cell" role="cell" aria-label="No session ${ts.label} ${day}"></div>`;
        return;
      }
      const inner = slotSessions.map(s => {
        const subj    = SUBJECT_MAP[s.subjectId];
        const teacher = TEACHER_MAP[s.teacherId];
        const room    = ROOM_MAP[s.roomId];
        const isConflictSession = isConflict && timetable.conflicts &&
          timetable.conflicts.some(c => c.affectedSessions.includes(s.id));
        const cssClass = isConflictSession ? 'session-conflict' : sessionCSSClass(s.type, s.targetGroup);
        const labBadge = s.type === 'practical'
          ? `<div class="tt-session-type">⚗ Lab ${s.targetGroup?.split('/')[1] || ''}</div>`
          : `<div class="tt-session-type">${s.type === 'tutorial' ? '✏ Tutorial' : s.type === 'lecture' ? '📖 Lecture' : '📚'}</div>`;
        const groupTag = s.targetGroup?.startsWith('EG_')
          ? ` <span style="font-size:9px;background:rgba(139,92,246,0.15);color:#5b21b6;border-radius:3px;padding:1px 4px;">${s.targetGroup.replace('EG_','')}</span>` : '';
        return `<div class="tt-session ${cssClass}"
            role="button" tabindex="0"
            onclick="showSessionModal('${s.id}','${timetable.id}')"
            onkeypress="if(event.key==='Enter')showSessionModal('${s.id}','${timetable.id}')"
            aria-label="${subj?.shortName || s.subjectId} ${s.type} ${day} ${ts.label}"
          >
          ${labBadge}
          <div class="tt-session-code">${subj?.shortName || s.subjectId}${groupTag}</div>
          <div class="tt-session-teacher">${teacher?.shortName || s.teacherId}</div>
          <div class="tt-session-room">${room?.name || s.roomId}</div>
        </div>`;
      }).join('');
      html += `<div class="tt-cell" role="cell">${inner}</div>`;
    });
  });

  grid.innerHTML = html;
}

function showSessionModal(sessionId, timetableId) {
  const tt = timetableId === MOCK_TIMETABLE_CONFLICT.id ? MOCK_TIMETABLE_CONFLICT : MOCK_TIMETABLE_VALID;
  const s  = tt.sessions.find(x => x.id === sessionId);
  if (!s) return;
  const subj    = SUBJECT_MAP[s.subjectId];
  const teacher = TEACHER_MAP[s.teacherId];
  const room    = ROOM_MAP[s.roomId];
  const ts      = TIME_SLOTS.find(t => t.id === s.slot);
  const isConflict = tt.status === 'diagnostic' && tt.conflicts?.some(c => c.affectedSessions.includes(s.id));

  const conflictHtml = isConflict
    ? `<div class="alert alert-error" role="alert" style="margin-top: 12px;">
        <span class="alert-icon">⛔</span>
        <span><strong>This session has a constraint violation.</strong> See the Conflicts panel for full details.</span>
       </div>` : '';

  openModal(`Session Details — ${s.day} ${ts?.label}`, `
    <table style="font-size: var(--text-sm); width:100%;">
      <tr><td style="padding:6px 0; color:var(--gray-500); width:140px;">Subject</td><td style="font-weight:600;">${subj?.name || s.subjectId}</td></tr>
      <tr><td style="padding:6px 0; color:var(--gray-500);">Type</td><td><span class="badge ${s.type === 'practical' ? 'badge-success' : s.type === 'tutorial' ? 'badge-info' : 'badge-brand'}">${s.type}</span></td></tr>
      <tr><td style="padding:6px 0; color:var(--gray-500);">Teacher</td><td style="font-weight:600;">${teacher?.name || s.teacherId}</td></tr>
      <tr><td style="padding:6px 0; color:var(--gray-500);">Room</td><td style="font-weight:600;">${room?.name || s.roomId} (cap. ${room?.capacity || '?'})</td></tr>
      <tr><td style="padding:6px 0; color:var(--gray-500);">Target Group</td><td style="font-weight:600; font-family: var(--font-mono); font-size: var(--text-xs);">${s.targetGroup}</td></tr>
      <tr><td style="padding:6px 0; color:var(--gray-500);">Day & Time</td><td style="font-weight:600;">${s.day}, ${ts?.label || s.slot}</td></tr>
      ${s.type === 'practical' ? `<tr><td style="padding:6px 0; color:var(--gray-500);">Duration</td><td>2 consecutive hours (${TIME_SLOTS.find(t=>t.id===s.labStart)?.label?.split('–')[0] || ''}–${TIME_SLOTS.find(t=>t.id===s.labEnd)?.label?.split('–')[1] || ''})</td></tr>` : ''}
      <tr><td style="padding:6px 0; color:var(--gray-500);">Session ID</td><td style="font-family: var(--font-mono); font-size: var(--text-xs); color: var(--gray-400);">${s.id}</td></tr>
    </table>
    ${conflictHtml}
    <div class="alert alert-warning" role="note" style="margin-top:12px;">
      <span class="alert-icon">⚠</span>
      <span style="font-size: var(--text-xs);">Mock data — not produced by the CP-SAT solver.</span>
    </div>
  `);
}

// ─── FILTERS ──────────────────────────────────────────────────────────────────
function applyFilters() {
  _currentFilterTeacher = document.getElementById('filter-teacher').value;
  _currentFilterRoom    = document.getElementById('filter-room').value;
  renderTimetableGrid(MOCK_TIMETABLE_VALID, null);
}
function resetFilters() {
  document.getElementById('filter-teacher').value = '';
  document.getElementById('filter-room').value    = '';
  document.getElementById('filter-year').value    = '3';
  document.getElementById('filter-division').value = 'A';
  _currentFilterTeacher = '';
  _currentFilterRoom    = '';
  renderTimetableGrid(MOCK_TIMETABLE_VALID, null);
}

// ─── CONFLICT PANEL ───────────────────────────────────────────────────────────
function renderConflictPanel() {
  const list    = document.getElementById('conflict-list');
  const summary = document.getElementById('conflict-summary');
  if (!list) return;

  const conflicts = MOCK_TIMETABLE_CONFLICT.conflicts || [];
  const errors    = conflicts.filter(c => c.severity === 'error');
  const warnings  = conflicts.filter(c => c.severity === 'warning');

  // Summary
  summary.innerHTML = `
    <div style="display:flex; align-items:center; justify-content:space-between;">
      <span class="text-sm font-semibold">Hard Violations (Level A)</span>
      <span class="badge badge-error">${errors.length}</span>
    </div>
    <div style="display:flex; align-items:center; justify-content:space-between;">
      <span class="text-sm font-semibold">Policy Issues / Incomplete</span>
      <span class="badge badge-warning">${warnings.length}</span>
    </div>
    <div class="divider" style="margin: 8px 0;"></div>
    <div class="publish-gate">
      <div class="publish-gate-title">🔒 Publication Blocked</div>
      <ul class="publish-gate-reasons">
        ${errors.map(e => `<li>${e.ruleId}: ${e.title}</li>`).join('')}
        ${warnings.map(w => `<li>${w.ruleId}: ${w.title}</li>`).join('')}
      </ul>
      <div style="font-size: var(--text-xs); color: #7f1d1d; margin-top: 4px;">
        Level A hard constraint violations cannot be relaxed or bypassed.
        All violations must be resolved before publication is permitted.
      </div>
    </div>
  `;

  // Conflict cards
  list.innerHTML = conflicts.map(c => `
    <div class="conflict-item ${c.severity === 'error' ? 'conflict-error' : 'conflict-warning'}"
         role="article" aria-label="Conflict: ${c.title}">
      <div class="conflict-header">
        <div>
          <div class="conflict-rule">Rule ${c.ruleId} &bull; Level ${c.level}</div>
          <div class="conflict-title">${c.severity === 'error' ? '⛔' : '⚠'} ${c.title}</div>
        </div>
        <span class="badge ${c.severity === 'error' ? 'badge-error' : 'badge-warning'}">
          ${c.severity === 'error' ? 'Hard Violation' : 'Warning'}
        </span>
      </div>
      <div class="conflict-desc">${c.description}</div>
      ${c.note ? `<div style="font-size: var(--text-xs); color: var(--gray-500); margin-top: 8px; font-style: italic;">ℹ ${c.note}</div>` : ''}
      ${c.affectedSessions.length > 0 ? `
        <div style="font-size: 10px; color: var(--gray-400); margin-top: 8px; font-family: var(--font-mono);">
          Affected sessions: ${c.affectedSessions.join(', ')}
        </div>` : ''}
      ${!c.canRelax ? `
        <div style="font-size: 10px; color: var(--error-500); margin-top: 6px; font-weight: 700;">
          ⛔ No relaxation permitted (Level A hard constraint)
        </div>` : ''}
    </div>
  `).join('');
}

// ─── TEACHERS TABLE ───────────────────────────────────────────────────────────
function renderTeachers() {
  const tbody = document.getElementById('teachers-tbody');
  if (!tbody || tbody.children.length > 0) return;
  TEACHERS.forEach(t => {
    const assignments = D.TEACHING_ASSIGNMENTS.filter(a => a.teacherId === t.id);
    tbody.innerHTML += `
      <tr>
        <td><code style="font-size: var(--text-xs); color: var(--gray-500);">${t.id}</code></td>
        <td><strong>${t.name}</strong></td>
        <td>${t.designation}</td>
        <td>${t.specializations.map(s => `<span class="badge badge-neutral" style="margin-right:2px;">${s}</span>`).join('')}</td>
        <td>${assignments.length > 0 ? `<span class="badge badge-brand">${assignments.length} assignment${assignments.length > 1 ? 's' : ''}</span>` : '<span class="text-muted">—</span>'}</td>
      </tr>`;
  });
}

// ─── ROOMS TABLE ──────────────────────────────────────────────────────────────
function renderRooms() {
  const classroomsTbody = document.getElementById('classrooms-tbody');
  const labsTbody       = document.getElementById('labs-tbody');
  if (classroomsTbody && classroomsTbody.children.length === 0) {
    ROOMS.filter(r => r.type === 'classroom').forEach(r => {
      classroomsTbody.innerHTML += `
        <tr>
          <td><code style="font-size: var(--text-xs);">${r.id}</code></td>
          <td>${r.name}</td>
          <td>${r.capacity}</td>
          <td>Floor ${r.floor}</td>
          <td><span class="badge badge-brand">Classroom</span></td>
        </tr>`;
    });
  }
  if (labsTbody && labsTbody.children.length === 0) {
    ROOMS.filter(r => r.type === 'laboratory').forEach(r => {
      labsTbody.innerHTML += `
        <tr>
          <td><code style="font-size: var(--text-xs);">${r.id}</code></td>
          <td>${r.name}</td>
          <td>${r.capacity}</td>
          <td>Floor ${r.floor}</td>
          <td>${(r.equipment || []).map(e => `<span class="badge badge-neutral" style="margin-right:2px;">${e}</span>`).join('')}</td>
        </tr>`;
    });
  }
}

function showRoomTab(tab) {
  ['classrooms','labs'].forEach(t => {
    document.getElementById(`rooms-tab-${t}`).classList.remove('active');
    document.getElementById(`rooms-tab-${t}`).classList.toggle('hidden', t !== tab);
    document.getElementById(`tab-${t}`).classList.remove('active');
    document.getElementById(`tab-${t}`).setAttribute('aria-selected', 'false');
  });
  document.getElementById(`rooms-tab-${tab}`).classList.add('active');
  document.getElementById(`tab-${tab}`).classList.add('active');
  document.getElementById(`tab-${tab}`).setAttribute('aria-selected', 'true');
}

// ─── REQUESTS ────────────────────────────────────────────────────────────────
let _requests = [...DEMO_REQUESTS];

function renderRequests() {
  const list = document.getElementById('requests-list');
  if (!list) return;
  const pending = _requests.filter(r => r.status === 'pending');

  // Update badge
  const badge = document.getElementById('request-count-badge');
  if (badge) badge.textContent = pending.length;
  document.getElementById('stat-requests').textContent = pending.length;

  list.innerHTML = _requests.map(r => `
    <div class="request-item" id="req-item-${r.id}">
      <div class="request-dot dot-${r.status}" aria-label="Status: ${r.status}"></div>
      <div style="flex:1;">
        <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
          <span class="request-type-badge badge ${r.type === 'reschedule' ? 'badge-brand' : r.type === 'substitution' ? 'badge-info' : 'badge-error'}">${r.type}</span>
          <span style="font-size: var(--text-xs); color: var(--gray-500);">from ${r.submitterName}</span>
          ${r.priority === 'high' ? `<span class="badge badge-error" style="font-size:9px;">HIGH PRIORITY</span>` : ''}
        </div>
        <div class="request-subject">${r.subject}</div>
        <div class="request-details">${r.details}</div>
        <div class="request-meta">
          <span>🕒 ${new Date(r.submittedAt).toLocaleString('en-IN',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})}</span>
          ${r.approvedAt ? `<span>✓ Approved by ${r.approvedBy}</span>` : ''}
        </div>
        ${r.status === 'pending' ? `
          <div style="display:flex; gap: 8px; margin-top: 10px;">
            <button class="btn btn-success btn-sm" onclick="handleRequest('${r.id}','approved')">✓ Approve</button>
            <button class="btn btn-danger btn-sm" onclick="handleRequest('${r.id}','rejected')">✕ Reject</button>
          </div>` : `
          <div style="margin-top: 8px;">
            <span class="status-pill ${r.status === 'approved' ? 'status-published' : 'status-diagnostic'}">
              <span class="status-dot"></span> ${r.status.charAt(0).toUpperCase() + r.status.slice(1)}
            </span>
          </div>`}
      </div>
    </div>
  `).join('');
}

function handleRequest(id, action) {
  const req = _requests.find(r => r.id === id);
  if (!req) return;
  req.status = action;
  req.approvedAt = new Date().toISOString();
  req.approvedBy = _adminUser?.name || 'Admin';
  renderRequests();
  showToast(`Request "${req.subject}" ${action}. (Simulated — no real repair operation executed.)`,
    action === 'approved' ? 'success' : 'warning');
}

// ─── GENERATE PANEL ───────────────────────────────────────────────────────────
let _selectedCandidate = 'valid';

function renderGeneratePanel() {
  selectCandidate(_selectedCandidate);
}

function selectCandidate(which) {
  _selectedCandidate = which;
  document.getElementById('candidate-valid').classList.toggle('selected', which === 'valid');
  document.getElementById('candidate-conflict').classList.toggle('selected', which === 'conflict');

  const tt = which === 'valid' ? MOCK_TIMETABLE_VALID : MOCK_TIMETABLE_CONFLICT;
  const subtitle = document.getElementById('validation-subtitle');
  const chip     = document.getElementById('validation-status-chip');
  const body     = document.getElementById('validation-body');
  const gate     = document.getElementById('publish-gate-panel');
  const pubBtn   = document.getElementById('btn-publish');

  subtitle.textContent = `Candidate ${which === 'valid' ? 1 : 2} — ${which === 'valid' ? 'Selected' : 'Diagnostic'}`;

  if (which === 'valid') {
    chip.innerHTML = `<span class="solver-status solver-feasible">✓ All checks passed</span>`;
    body.innerHTML = `
      <div class="alert alert-success" role="note" style="margin-bottom:12px;">
        <span class="alert-icon">✓</span>
        <span><strong>Candidate 1 passes all validation checks.</strong> 27 sessions placed. 0 hard violations. 0 policy violations.</span>
      </div>
      <div class="alert alert-warning" role="note" style="margin-bottom:12px;">
        <span class="alert-icon">⚠</span>
        <span><strong>Mock candidate only.</strong> This timetable was hand-crafted for demo purposes, not produced by the real CP-SAT solver. No actual optimization occurred.</span>
      </div>
      <table style="font-size: var(--text-xs); width:100%;">
        <tr><td style="color:var(--gray-500);padding:4px 0;">Solver status</td><td style="font-weight:600;">Mock — not solver-generated</td></tr>
        <tr><td style="color:var(--gray-500);padding:4px 0;">Hard violations (Level A)</td><td style="font-weight:600; color: var(--success-500);">0</td></tr>
        <tr><td style="color:var(--gray-500);padding:4px 0;">Policy violations (Level B)</td><td style="font-weight:600; color: var(--success-500);">0</td></tr>
        <tr><td style="color:var(--gray-500);padding:4px 0;">Unscheduled requirements</td><td style="font-weight:600; color: var(--success-500);">0</td></tr>
        <tr><td style="color:var(--gray-500);padding:4px 0;">Total sessions</td><td style="font-weight:600;">27</td></tr>
        <tr><td style="color:var(--gray-500);padding:4px 0;">Lunch rule</td><td><span class="badge badge-success">✓ Respected</span></td></tr>
        <tr><td style="color:var(--gray-500);padding:4px 0;">Lab continuity</td><td><span class="badge badge-success">✓ 2-hour blocks</span></td></tr>
        <tr><td style="color:var(--gray-500);padding:4px 0;">Elective conflicts</td><td><span class="badge badge-success">✓ No overlap</span></td></tr>
      </table>`;
    gate.innerHTML = '';
    pubBtn.disabled = false;
    pubBtn.className = 'btn btn-success btn-lg';
    pubBtn.style.flex = '1';
  } else {
    chip.innerHTML = `<span class="solver-status solver-infeasible">⛔ Violations found</span>`;
    body.innerHTML = `
      <div class="alert alert-error" role="alert" style="margin-bottom:12px;">
        <span class="alert-icon">⛔</span>
        <span><strong>Candidate 2 is INCOMPLETE.</strong> 3 hard constraint violations (Level A). 1 unscheduled requirement. Publication is blocked.</span>
      </div>
      <table style="font-size: var(--text-xs); width:100%;">
        <tr><td style="color:var(--gray-500);padding:4px 0;">Solver status</td><td style="font-weight:600; color: var(--error-500);">Diagnostic Draft — INCOMPLETE</td></tr>
        <tr><td style="color:var(--gray-500);padding:4px 0;">Hard violations (Level A)</td><td style="font-weight:600; color: var(--error-500);">3</td></tr>
        <tr><td style="color:var(--gray-500);padding:4px 0;">Unscheduled requirements</td><td style="font-weight:600; color: var(--error-500);">1</td></tr>
        <tr><td style="color:var(--gray-500);padding:4px 0;">A01 — Teacher double-booking</td><td><span class="badge badge-error">Violated</span></td></tr>
        <tr><td style="color:var(--gray-500);padding:4px 0;">A03/A04 — Student overlap</td><td><span class="badge badge-error">Violated</span></td></tr>
        <tr><td style="color:var(--gray-500);padding:4px 0;">A08 — Lab spans lunch</td><td><span class="badge badge-error">Violated</span></td></tr>
      </table>`;
    gate.innerHTML = `
      <div class="publish-gate" style="margin-top: 12px;" role="alert">
        <div class="publish-gate-title">🔒 Publication Blocked — INCOMPLETE Candidate</div>
        <ul class="publish-gate-reasons">
          <li>A01: Prof. Vikram Singh double-booked Monday 09:00–10:00</li>
          <li>A03/A04: EG_CV and EG_NLP overlap — simultaneous scheduling prohibited</li>
          <li>A08: ML Lab (B1) spans Div-3A lunch slot (12:00–14:00)</li>
          <li>Incomplete: DL Practical (B3) not placed</li>
        </ul>
        <div style="font-size: var(--text-xs); color: #7f1d1d; margin-top:4px;">
          A diagnostic draft can never be published. All Level A violations must be resolved first.
          Level A hard constraints cannot be relaxed through the UI.
        </div>
      </div>`;
    pubBtn.disabled = true;
    pubBtn.className = 'btn btn-success btn-lg';
    pubBtn.style.flex = '1';
  }
}

function simulateGenerate() {
  const btn  = document.getElementById('btn-generate-new');
  const icon = document.getElementById('gen-btn-icon');
  const text = document.getElementById('gen-btn-text');
  btn.classList.add('loading');
  icon.innerHTML = '<span class="spinner">⟳</span>';
  text.textContent = 'Simulating…';

  setTimeout(() => {
    btn.classList.remove('loading');
    icon.textContent = '⚙';
    text.textContent = 'Simulate Generate';
    showToast('Mock candidates loaded. Note: No real CP-SAT solver was invoked.', 'info');
    selectCandidate('valid');
  }, 1800);
}

function simulatePublish() {
  if (_selectedCandidate !== 'valid') {
    showToast('Cannot publish a diagnostic draft. Resolve all violations first.', 'error');
    return;
  }
  showToast('⚠ Simulated publish: In the real system, this would write to the database, notify teachers and students, and update the published version. No real action was performed.', 'success');
}

// ─── OVERVIEW: ELECTIVE GROUPS ────────────────────────────────────────────────
function renderElectiveGroups() {
  const container = document.getElementById('elective-groups-list');
  if (!container) return;
  ENROLLMENT_GROUPS.forEach(eg => {
    const subj = SUBJECTS.find(s => s.id === eg.subjectId);
    container.innerHTML += `
      <div style="display:flex; align-items:center; justify-content:space-between; padding: 8px 0; border-bottom: 1px solid var(--gray-100);">
        <div>
          <div style="font-size: var(--text-sm); font-weight: 600;">${eg.name}</div>
          <div style="font-size: var(--text-xs); color: var(--gray-500);">${subj?.name || eg.subjectId} &bull; ${eg.studentCount} students</div>
        </div>
        <div>
          ${eg.conflicts.length > 0
            ? eg.conflicts.map(c => `<span class="badge badge-error" style="font-size:9px;">Conflicts: ${c}</span>`).join('')
            : `<span class="badge badge-success">No conflicts</span>`
          }
        </div>
      </div>`;
  });
}

// ─── OVERVIEW STATS ───────────────────────────────────────────────────────────
function initOverview() {
  document.getElementById('stat-divisions').textContent = SUMMARY_STATS.totalDivisions;
  document.getElementById('stat-teachers').textContent  = SUMMARY_STATS.totalTeachers;
  document.getElementById('stat-rooms').textContent     = SUMMARY_STATS.totalRooms;
  document.getElementById('stat-requests').textContent  = SUMMARY_STATS.pendingRequests;
  document.getElementById('overview-sessions').textContent = SUMMARY_STATS.totalSessions;
  renderElectiveGroups();
}

// ─── KEYBOARD NAVIGATION ──────────────────────────────────────────────────────
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('keypress', e => { if (e.key === 'Enter' || e.key === ' ') item.click(); });
});

// ─── INIT ─────────────────────────────────────────────────────────────────────
initOverview();
renderTimetableGrid(MOCK_TIMETABLE_VALID, null); // pre-render for filters

  // ─── EXPOSE TO WINDOW ────────────────────────────────────────────────────────
  window.showPanel = showPanel;
  window.signOut = signOut;
  window.showToast = showToast;
  window.openModal = openModal;
  window.closeModal = closeModal;
  window.showSessionModal = showSessionModal;
  window.applyFilters = applyFilters;
  window.resetFilters = resetFilters;
  window.renderConflictPanel = renderConflictPanel;
  window.renderTeachers = renderTeachers;
  window.renderRooms = renderRooms;
  window.showRoomTab = showRoomTab;
  window.renderRequests = renderRequests;
  window.handleRequest = handleRequest;
  window.renderGeneratePanel = renderGeneratePanel;
  window.selectCandidate = selectCandidate;
  window.simulateGenerate = simulateGenerate;
  window.simulatePublish = simulatePublish;
  window.initOverview = initOverview;
})();
