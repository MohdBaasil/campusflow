// Auth guard — redirect to login if not staff
if (localStorage.getItem("user_type") !== "staff") {
    window.location.href = "login.html";
}

/**
 * students.js – View Registered Students
 * Handles fetching, searching, filtering, and student detail modal.
 */

const API = window.location.protocol === 'file:' ? 'http://127.0.0.1:5000' : '';
let allStudents = [];

// ─── Init ────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setDate();
  loadStudents();

  // Live search
  document.getElementById('search-input').addEventListener('input', renderStudents);
  document.getElementById('dept-filter').addEventListener('change', renderStudents);
  document.getElementById('face-filter').addEventListener('change', renderStudents);

  // Close modal on overlay click
  document.getElementById('student-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeModal();
  });

  // Close modal on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });
});


function setDate() {
  const now = new Date();
  const opts = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
  document.getElementById('topbar-date').textContent = now.toLocaleDateString('en-US', opts);
}


// ─── Fetch Students ──────────────────────────────
async function loadStudents() {
  try {
    const res = await fetch(`${API}/api/students`);
    if (!res.ok) throw new Error('Failed to fetch students');
    allStudents = await res.json();
    populateDeptFilter();
    updateSummaryStats();
    renderStudents();
  } catch (err) {
    console.error(err);
    showToast('Failed to load students', 'error');
  }
}


function populateDeptFilter() {
  const depts = [...new Set(allStudents.map(s => s.department))].sort();
  const sel = document.getElementById('dept-filter');
  // Clear existing options except "All"
  sel.innerHTML = '<option value="All">All Departments</option>';
  depts.forEach(d => {
    const opt = document.createElement('option');
    opt.value = d;
    opt.textContent = d;
    sel.appendChild(opt);
  });
}


function updateSummaryStats() {
  const total = allStudents.length;
  const enrolled = allStudents.filter(s => s.face_count > 0).length;
  const missing = total - enrolled;
  const depts = new Set(allStudents.map(s => s.department)).size;

  document.getElementById('stat-total').textContent = total;
  document.getElementById('stat-enrolled').textContent = enrolled;
  document.getElementById('stat-missing').textContent = missing;
  document.getElementById('stat-depts').textContent = depts;
}


// ─── Render Cards ────────────────────────────────
function renderStudents() {
  const query = document.getElementById('search-input').value.toLowerCase().trim();
  const deptFilter = document.getElementById('dept-filter').value;
  const faceFilter = document.getElementById('face-filter').value;

  let filtered = allStudents.filter(s => {
    const matchSearch = !query ||
      s.name.toLowerCase().includes(query) ||
      s.roll_number.toLowerCase().includes(query) ||
      s.department.toLowerCase().includes(query);

    const matchDept = deptFilter === 'All' || s.department === deptFilter;

    const matchFace = faceFilter === 'All' ||
      (faceFilter === 'enrolled' && s.face_count > 0) ||
      (faceFilter === 'missing' && s.face_count === 0);

    return matchSearch && matchDept && matchFace;
  });

  const grid = document.getElementById('students-grid');

  if (filtered.length === 0) {
    grid.innerHTML = `
      <div style="grid-column: 1/-1;">
        <div class="empty-state">
          <div class="empty-icon">🔍</div>
          <div class="empty-title">No students found</div>
          <div class="empty-sub">Try adjusting your search or filters.</div>
        </div>
      </div>`;
    return;
  }

  grid.innerHTML = filtered.map(s => {
    const initials = s.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
    const faceStatus = s.face_count > 0
      ? `<span class="tag-dot green"></span> ${s.face_count} photo${s.face_count > 1 ? 's' : ''}`
      : `<span class="tag-dot orange"></span> No photos`;
    const regDate = s.created_at
      ? new Date(s.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
      : '—';

    return `
      <div class="student-card" onclick="openStudentDetail(${s.id})" title="Click to view details">
        <div class="student-card-header">
          <div class="student-avatar">${initials}</div>
          <div>
            <div class="student-card-name">${escHtml(s.name)}</div>
            <div class="student-card-roll">${escHtml(s.roll_number)}</div>
          </div>
        </div>
        <div class="student-card-meta">
          <div class="student-meta-tag"><span class="tag-dot purple"></span> ${escHtml(s.department)}</div>
          <div class="student-meta-tag">${faceStatus}</div>
          <div class="student-meta-tag"><span class="tag-dot blue"></span> ${regDate}</div>
        </div>
      </div>`;
  }).join('');
}


// ─── Student Detail Modal ────────────────────────
async function openStudentDetail(studentId) {
  const student = allStudents.find(s => s.id === studentId);
  if (!student) return;

  const initials = student.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();

  // Fetch attendance records for this student
  let records = [];
  try {
    const res = await fetch(`${API}/api/attendance/records`);
    if (res.ok) {
      const all = await res.json();
      records = all.filter(r => r.student_id === studentId);
    }
  } catch (e) { console.warn('Could not load attendance records', e); }

  // Compute stats
  const totalAttendance = records.length;
  const uniqueDates = new Set(records.map(r => r.date)).size;
  const subjects = {};
  records.forEach(r => {
    subjects[r.subject] = (subjects[r.subject] || 0) + 1;
  });

  // Recent 10 records
  const recent = records.slice(0, 10);

  const body = document.getElementById('modal-body');
  body.innerHTML = `
    <div class="detail-header">
      <div class="detail-avatar">${initials}</div>
      <div>
        <div class="detail-name">${escHtml(student.name)}</div>
        <div class="detail-roll">${escHtml(student.roll_number)} · ${escHtml(student.department)}</div>
      </div>
    </div>

    <div class="detail-stats-row">
      <div class="detail-stat">
        <div class="detail-stat-val" style="color:var(--purple);">${student.face_count}</div>
        <div class="detail-stat-label">Face Photos</div>
      </div>
      <div class="detail-stat">
        <div class="detail-stat-val" style="color:var(--green);">${totalAttendance}</div>
        <div class="detail-stat-label">Total Records</div>
      </div>
      <div class="detail-stat">
        <div class="detail-stat-val" style="color:var(--blue);">${uniqueDates}</div>
        <div class="detail-stat-label">Days Present</div>
      </div>
      <div class="detail-stat">
        <div class="detail-stat-val" style="color:var(--orange);">${Object.keys(subjects).length}</div>
        <div class="detail-stat-label">Subjects</div>
      </div>
    </div>

    ${Object.keys(subjects).length > 0 ? `
    <div class="detail-section-title">📚 Subject Breakdown</div>
    <div style="display:flex; flex-wrap:wrap; gap:8px; margin-bottom:20px;">
      ${Object.entries(subjects).sort((a,b)=>b[1]-a[1]).map(([subj, cnt]) => `
        <span class="badge badge-purple">${escHtml(subj)}: ${cnt}</span>
      `).join('')}
    </div>` : ''}

    <div class="detail-section-title">🕐 Recent Attendance <span class="count-badge">${recent.length}</span></div>
    ${recent.length > 0 ? `
    <div class="table-wrapper" style="max-height:260px; overflow-y:auto;">
      <table>
        <thead><tr>
          <th>Subject</th><th>Date</th><th>Time</th><th>Status</th><th>Confidence</th>
        </tr></thead>
        <tbody>
          ${recent.map(r => `
          <tr>
            <td>${escHtml(r.subject)}</td>
            <td>${r.date}</td>
            <td>${r.time}</td>
            <td><span class="badge badge-success">✓ ${r.status}</span></td>
            <td><span class="badge badge-blue">${r.confidence || '–'}%</span></td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>` : `
    <div class="empty-state" style="padding:28px;">
      <div class="empty-icon" style="font-size:32px;">📋</div>
      <div class="empty-title" style="font-size:14px;">No attendance records yet</div>
    </div>`}

    <div style="margin-top:8px; font-size:11px; color:var(--text-muted);">
      Registered on: ${student.created_at ? new Date(student.created_at).toLocaleString() : '—'}
    </div>

    <div class="detail-actions">
      <a href="enroll.html" class="btn btn-primary btn-sm">📷 Enroll Face</a>
      <button class="btn btn-danger btn-sm" onclick="deleteStudent(${student.id}, '${escHtml(student.name).replace(/'/g, "\\'")}')">🗑️ Delete</button>
    </div>
  `;

  document.getElementById('student-modal').classList.add('open');
}


function closeModal() {
  document.getElementById('student-modal').classList.remove('open');
}


// ─── Delete Student ──────────────────────────────
async function deleteStudent(id, name) {
  if (!confirm(`Are you sure you want to delete "${name}"?\n\nThis will remove all their face data and attendance records.`)) return;

  try {
    const res = await fetch(`${API}/api/students/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Delete failed');
    showToast(`${name} deleted successfully`, 'success');
    closeModal();
    loadStudents();
  } catch (err) {
    showToast('Failed to delete student', 'error');
  }
}


// ─── Export CSV ──────────────────────────────────
function exportStudents() {
  const headers = ['ID', 'Name', 'Roll Number', 'Department', 'Face Photos', 'Registered'];
  const rows = allStudents.map(s => [
    s.id,
    `"${s.name}"`,
    s.roll_number,
    `"${s.department}"`,
    s.face_count,
    s.created_at || ''
  ]);

  let csv = headers.join(',') + '\n';
  rows.forEach(r => csv += r.join(',') + '\n');

  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `students_${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
  showToast('Students exported to CSV', 'success');
}


// ─── Helpers ─────────────────────────────────────
function escHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

function showToast(msg, type = 'info') {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  t.innerHTML = `<span>${icons[type] || ''}</span><span>${msg}</span>`;
  c.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 3500);
}
