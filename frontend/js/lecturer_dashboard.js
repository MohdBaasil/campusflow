/**
 * lecturer_dashboard.js
 * Controls dashboard rendering, loads profile, lists subjects, handles starting sessions.
 */

const API = window.location.protocol === 'file:' ? 'http://127.0.0.1:5000' : '';
let lecturerData = null;

document.addEventListener('DOMContentLoaded', () => {
  // Load lecturer info
  const stored = localStorage.getItem('user_data');
  if (stored) {
    lecturerData = JSON.parse(stored);
    document.getElementById('lecturer-welcome').textContent = `Welcome, ${lecturerData.name}`;
    document.getElementById('hero-lecturer-name').textContent = lecturerData.name;
    document.getElementById('hero-lecturer-dept').textContent = `Department of ${lecturerData.department} (ID: ${lecturerData.employee_id})`;
  }
  
  loadDashboardData();
  loadSubjects();
});

// Alerts & Toasts
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

// Fetch dashboard stats and session history
async function loadDashboardData() {
  if (!lecturerData) return;
  
  try {
    const res = await fetch(`${API}/api/lecturer/dashboard?lecturer_id=${lecturerData.id}`);
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
          <td><strong>${s.subject_code}</strong> - ${s.subject_name}</td>
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
          <td colspan="5" style="text-align: center; color: var(--text-muted);">
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
          <td><strong>${s.subject_code}</strong> - ${s.subject_name}</td>
          <td><span class="badge badge-outline">${s.session_type}</span></td>
          <td>${s.topic_covered || '<span style="color: var(--text-muted);">Not specified</span>'}</td>
          <td>${s.start_time} - ${s.end_time || ''}</td>
          <td><span class="badge badge-blue">${s.attendance_count || 0} Records</span></td>
        `;
        recentBody.appendChild(tr);
      });
    } else {
      recentBody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align: center; color: var(--text-muted);">
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

// Fetch subjects and load select dropdown & list
async function loadSubjects() {
  if (!lecturerData) return;
  
  try {
    const res = await fetch(`${API}/api/subjects/list?department=${lecturerData.department}`);
    const subjects = await res.json();
    
    // Filter subjects where this lecturer is assigned
    const mySubjects = subjects.filter(s => s.lecturer_id === lecturerData.id);
    
    // Populate select dropdown
    const select = document.getElementById('session-subject');
    select.innerHTML = '<option value="">— Select Subject —</option>';
    
    // Populate list
    const listBody = document.getElementById('subjects-list-body');
    listBody.innerHTML = '';
    
    document.getElementById('stat-subjects-count').textContent = mySubjects.length;
    
    if (mySubjects.length > 0) {
      mySubjects.forEach(s => {
        // Add to dropdown
        const opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = `${s.code} — ${s.name}`;
        select.appendChild(opt);
        
        // Add to list
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
          <td colspan="4" style="text-align: center; color: var(--text-muted);">
            No subjects assigned to you. Contact admin.
          </td>
        </tr>
      `;
    }
  } catch (err) {
    console.error('Failed to load subjects:', err);
    toast('❌ Error loading subjects list.', 'error');
  }
}

// Helper to pre-fill and start session
function quickStartSubject(subjId) {
  document.getElementById('session-subject').value = subjId;
  document.getElementById('session-topic').focus();
}

// Form handler for starting class session
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
    const res = await fetch(`${API}/api/class-sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        subject_id: parseInt(subjectId),
        lecturer_id: lecturerData.id,
        topic_covered: topicCovered,
        session_type: sessionType
      })
    });
    const data = await res.json();
    
    if (data.success) {
      toast('🚀 Class session started successfully!', 'success');
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
    btn.innerHTML = '🚀 Start Live Camera Session';
  }
}
