/**
 * notifications.js
 * Controls broadcasting alerts to students and displaying sent logs feed.
 */

const API = window.location.protocol === 'file:' ? 'http://127.0.0.1:5000' : '';
let allStudents = [];
let filteredStudents = [];

document.addEventListener('DOMContentLoaded', () => {
  loadNotificationsList();
  loadAllStudentsData();
});

// Toast helper
function toast(msg, type = 'info') {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  t.innerHTML = `<span>${icons[type] || ''}</span><span>${msg}</span>`;
  c.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 3500);
}

function showFormMsg(msg, type = 'error') {
  document.getElementById('alert-form-msg').innerHTML =
    `<div class="alert alert-${type}" style="margin-bottom:16px;">${msg}</div>`;
}

// Pre-load all students
async function loadAllStudentsData() {
  try {
    const res = await fetch(`${API}/api/students`);
    allStudents = await res.json();
  } catch (err) {
    console.error('Error pre-loading students:', err);
  }
}

// Load students on department dropdown change
function onDeptChange() {
  const dept = document.getElementById('select-dept').value;
  const container = document.getElementById('student-select-container');
  
  if (!dept) {
    container.innerHTML = `
      <div style="text-align: center; color: var(--text-muted); font-size: 12px; padding: 20px 0;">
        Select a department first.
      </div>
    `;
    filteredStudents = [];
    return;
  }
  
  filteredStudents = allStudents.filter(s => s.department === dept);
  
  if (filteredStudents.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; color: var(--text-muted); font-size: 12px; padding: 20px 0;">
        No registered students found in this department.
      </div>
    `;
    return;
  }
  
  container.innerHTML = '';
  filteredStudents.forEach(s => {
    const div = document.createElement('div');
    div.className = 'student-selector-item';
    div.innerHTML = `
      <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; width: 100%;">
        <input type="checkbox" class="student-select-checkbox" value="${s.id}" />
        <span><strong>${s.roll_number}</strong> — ${s.name}</span>
      </label>
    `;
    container.appendChild(div);
  });
}

// Helper: Check/uncheck all checkboxes
function selectAllStudents(checked) {
  document.querySelectorAll('.student-select-checkbox').forEach(cb => {
    cb.checked = checked;
  });
}

// Fetch and render sent notifications log list
async function loadNotificationsList() {
  const typeFilter = document.getElementById('filter-notif-type').value;
  let url = `${API}/api/notifications?`;
  
  if (typeFilter && typeFilter !== 'All') {
    url += `type=${typeFilter}`;
  }
  
  try {
    const res = await fetch(url);
    const notifications = await res.json();
    
    // Set total badge count
    document.getElementById('stat-total-sent').textContent = `${notifications.length} sent`;
    
    const container = document.getElementById('notifications-list-container');
    container.innerHTML = '';
    
    if (notifications.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; color: var(--text-muted); font-size: 14px; padding: 50px 0;">
          No sent notifications found in logs.
        </div>
      `;
      return;
    }
    
    notifications.forEach(n => {
      let badgeClass = 'badge-purple';
      if (n.type === 'absence') badgeClass = 'badge-danger';
      else if (n.type === 'low_attendance') badgeClass = 'badge-orange';
      else if (n.type === 'marks_published') badgeClass = 'badge-success';
      
      const dateStr = new Date(n.sent_at).toLocaleString();
      const statusBadge = n.status === 'sent' 
        ? `<span class="badge badge-success">Sent (Email)</span>`
        : `<span class="badge badge-danger">Failed (${n.status})</span>`;
        
      const card = document.createElement('div');
      card.className = 'notif-card';
      card.innerHTML = `
        <div class="notif-card-header">
          <span class="badge ${badgeClass}">${n.type.toUpperCase().replace('_', ' ')}</span>
          <span class="notif-card-date">${dateStr}</span>
        </div>
        <div class="notif-card-title" style="margin-bottom: 6px;">
          To: <strong>${n.student_name} (${n.roll_number})</strong>
        </div>
        <div class="notif-card-body">
          ${n.message}
        </div>
        <div style="margin-top: 10px; display: flex; justify-content: space-between; align-items: center;">
          ${statusBadge}
          <button class="btn btn-outline btn-sm" onclick="resendAlert(${n.id})" style="padding: 4px 10px; font-size: 11px;">
            🔄 Resend
          </button>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error(err);
    toast('❌ Error loading notifications feed.', 'error');
  }
}

// Resend notification
async function resendAlert(notifId) {
  try {
    const res = await fetch(`${API}/api/notifications/${notifId}/resend`, {
      method: 'POST'
    });
    const data = await res.json();
    if (data.success) {
      toast('🔄 Notification resend successful!', 'success');
      loadNotificationsList();
    } else {
      toast(`❌ Resend failed: ${data.error}`, 'error');
    }
  } catch (err) {
    console.error(err);
    toast('❌ Resend connection error.', 'error');
  }
}

// Send broadcast notice
async function sendBroadcast() {
  document.getElementById('alert-form-msg').innerHTML = '';
  
  const checkboxes = document.querySelectorAll('.student-select-checkbox:checked');
  const type = document.getElementById('input-notif-type').value;
  const message = document.getElementById('input-message').value.trim();
  
  if (checkboxes.length === 0) {
    showFormMsg('⚠️ Please select at least one student to broadcast to.', 'warning');
    return;
  }
  
  if (!message) {
    showFormMsg('⚠️ Message body cannot be empty.', 'warning');
    return;
  }
  
  const studentIds = [];
  checkboxes.forEach(cb => {
    studentIds.push(parseInt(cb.value));
  });
  
  const btn = document.getElementById('btn-send-notif');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Broadcasting...';
  
  try {
    const res = await fetch(`${API}/api/notifications/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        student_ids: studentIds,
        type: type,
        message: message
      })
    });
    const data = await res.json();
    
    if (data.success) {
      toast('🎉 Broadcast notices sent successfully!', 'success');
      document.getElementById('input-message').value = '';
      selectAllStudents(false);
      loadNotificationsList(); // Reload list
    } else {
      showFormMsg(`❌ Error: ${data.error}`, 'error');
    }
  } catch (err) {
    console.error(err);
    showFormMsg('❌ Connection error broadcasting notice.', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '✉️ Broadcast Email Alert';
  }
}
