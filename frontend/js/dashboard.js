/**
 * dashboard.js — Unified Staff/Lecturer Dashboard
 * Shows session management, subjects, active sessions and history.
 */

// Auth guard — redirect to login if not staff or lecturer
const _ut = localStorage.getItem('user_type');
if (_ut !== 'staff' && _ut !== 'lecturer') {
  window.location.href = 'login.html';
}

function logout() {
  localStorage.clear();
  window.location.href = 'login.html';
}

const API = window.location.protocol === 'file:' ? 'http://127.0.0.1:5000' : '';
let userData = null;

// ── Toast ─────────────────────────────────────────────────────────
function toast(msg, type = 'info') {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  t.innerHTML = `<span>${icons[type] || ''}</span><span>${msg}</span>`;
  c.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 3500);
}

function showSessionAlert(msg, type = 'error') {
  document.getElementById('session-alert').innerHTML =
    `<div class="alert alert-${type}" style="margin-bottom:16px;">${msg}</div>`;
}

// ── Init ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Set date
  document.getElementById('current-date-str').textContent = new Date().toLocaleDateString('en-US', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
  });

  // Load user info from localStorage
  const stored = localStorage.getItem('user_data');
  const userType = localStorage.getItem('user_type');

  if (stored) {
    userData = JSON.parse(stored);

    if (userType === 'lecturer') {
      // Lecturer: use their name and department
      document.getElementById('topbar-welcome').textContent = `Welcome, ${userData.name}`;
      document.getElementById('hero-user-name').textContent = userData.name;
      document.getElementById('hero-user-dept').textContent =
        `Department of ${userData.department} (ID: ${userData.employee_id})`;
    } else {
      // Staff admin
      document.getElementById('topbar-welcome').textContent = `Welcome, ${userData.username || 'Admin'}`;
      document.getElementById('hero-user-name').textContent = userData.username || 'Administrator';
      document.getElementById('hero-user-dept').textContent = 'Staff Administrator — CampusFlow';
    }
  }

  loadDashboardData();
  loadSubjects();
});

// ── Load Dashboard Stats + Active/Recent Sessions ─────────────────
async function loadDashboardData() {
  try {
    // Build URL depending on user type
    const userType = localStorage.getItem('user_type');
    let url = `${API}/api/lecturer/dashboard`;
    if (userData) {
      url += userType === 'lecturer'
        ? `?lecturer_id=${userData.id}`
        : `?lecturer_id=`; // staff: fetch all sessions
    }

    const res = await fetch(url);
    if (!res.ok) throw new Error('Server error');
    const data = await res.json();

    // Stats
    document.getElementById('stat-today-sessions').textContent = data.today_count || 0;
    document.getElementById('stat-students-count').textContent = data.total_students || 0;

    // Active Sessions
    const activeBody = document.getElementById('active-sessions-body');
    activeBody.innerHTML = '';
    if (data.active_sessions && data.active_sessions.length > 0) {
      data.active_sessions.forEach(s => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${s.subject_code}</strong> — ${s.subject_name}</td>
          <td><span class="badge badge-purple">${s.session_type}</span></td>
          <td>${s.start_time}</td>
          <td><span class="badge badge-success">Active</span></td>
          <td>
            <a href="class_session.html?session_id=${s.id}" class="btn btn-primary btn-sm">
              📹 Monitor
            </a>
          </td>
        `;
        activeBody.appendChild(tr);
      });
    } else {
      activeBody.innerHTML = `
        <tr>
          <td colspan="5" style="text-align:center; color:var(--text-muted); padding:24px;">
            No active class sessions. Start one above!
          </td>
        </tr>
      `;
    }

    // Recent Sessions
    const recentBody = document.getElementById('recent-sessions-body');
    recentBody.innerHTML = '';
    const completed = (data.recent_sessions || []).filter(s => s.status === 'completed');
    if (completed.length > 0) {
      completed.forEach(s => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${s.date}</td>
          <td><strong>${s.subject_code}</strong> — ${s.subject_name}</td>
          <td><span class="badge badge-outline">${s.session_type}</span></td>
          <td>${s.topic_covered || '<span style="color:var(--text-muted);">Not specified</span>'}</td>
          <td>${s.start_time} — ${s.end_time || ''}</td>
          <td><span class="badge badge-blue">${s.attendance_count || 0} Records</span></td>
        `;
        recentBody.appendChild(tr);
      });
    } else {
      recentBody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align:center; color:var(--text-muted); padding:24px;">
            No completed sessions in log.
          </td>
        </tr>
      `;
    }

  } catch (err) {
    console.error('Failed to load dashboard data:', err);
    toast('❌ Error loading dashboard statistics.', 'error');
  }
}

// ── Load Subjects ─────────────────────────────────────────────────
async function loadSubjects() {
  try {
    const userType = localStorage.getItem('user_type');
    let url = `${API}/api/subjects/list`;
    if (userData && userData.department) {
      url += `?department=${encodeURIComponent(userData.department)}`;
    }

    const res = await fetch(url);
    if (!res.ok) throw new Error('Server error');
    const subjects = await res.json();

    // For lecturer: only their subjects. For staff: show all.
    const mySubjects = (userType === 'lecturer' && userData)
      ? subjects.filter(s => s.lecturer_id === userData.id)
      : subjects;

    document.getElementById('stat-subjects-count').textContent = mySubjects.length;

    // Populate dropdown
    const select = document.getElementById('session-subject');
    select.innerHTML = '<option value="">— Select Subject —</option>';

    // Populate table
    const listBody = document.getElementById('subjects-list-body');
    listBody.innerHTML = '';

    if (mySubjects.length > 0) {
      mySubjects.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = `${s.code} — ${s.name}`;
        select.appendChild(opt);

        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${s.code}</strong></td>
          <td>${s.name}</td>
          <td>Semester ${s.semester}</td>
          <td>
            <button class="btn btn-outline btn-sm" onclick="quickStartSubject(${s.id})">
              🚀 Start
            </button>
          </td>
        `;
        listBody.appendChild(tr);
      });
    } else {
      listBody.innerHTML = `
        <tr>
          <td colspan="4" style="text-align:center; color:var(--text-muted); padding:24px;">
            No subjects assigned. Contact admin.
          </td>
        </tr>
      `;
    }
  } catch (err) {
    console.error('Failed to load subjects:', err);
    toast('❌ Error loading subjects list.', 'error');
  }
}

// ── Quick-start a subject ─────────────────────────────────────────
function quickStartSubject(subjId) {
  document.getElementById('session-subject').value = subjId;
  document.getElementById('session-topic').focus();
}

// ── Start New Session ─────────────────────────────────────────────
async function startNewSession() {
  const subjectId = document.getElementById('session-subject').value;
  const sessionType = document.getElementById('session-type').value;
  const topicCovered = document.getElementById('session-topic').value.trim();

  if (!subjectId) {
    showSessionAlert('⚠️ Please select a subject first.', 'warning');
    return;
  }

  const btn = document.getElementById('start-session-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Starting Session...';

  try {
    // Use lecturer id if available, otherwise use 1 as default staff
    const lecturerId = (userData && userData.id) ? userData.id : 1;

    const res = await fetch(`${API}/api/class-sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        subject_id: parseInt(subjectId),
        lecturer_id: lecturerId,
        topic_covered: topicCovered,
        session_type: sessionType
      })
    });
    const data = await res.json();

    if (data.success) {
      toast('🎥 Class session started successfully!', 'success');
      setTimeout(() => {
        window.location.href = `class_session.html?session_id=${data.session.id}`;
      }, 600);
    } else {
      showSessionAlert(`❌ ${data.error}`, 'error');
    }
  } catch (err) {
    showSessionAlert('❌ Connection error. Failed to start session.', 'error');
    console.error(err);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '🎥 Start Live Camera Session';
  }
}
