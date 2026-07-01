/**
 * student_dashboard.js
 * Controls the Student Portal dashboard, tab navigation, fetching marks, logs, and notifications.
 */

const API = window.location.protocol === 'file:' ? 'http://127.0.0.1:5000' : '';
let studentData = null;

document.addEventListener('DOMContentLoaded', () => {
  const stored = localStorage.getItem('user_data');
  if (stored) {
    studentData = JSON.parse(stored);
  }
  
  if (!studentData) {
    toast('❌ Error loading profile data.', 'error');
    return;
  }
  
  setDate();
  loadStudentProfile();
  loadStudentStats();
  loadStudentNotifications();
  loadStudentMarks();
  loadStudentAttendanceLogs();
});

// Set topbar date
function setDate() {
  const now = new Date();
  const opts = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
  document.getElementById('topbar-date').textContent = now.toLocaleDateString('en-US', opts);
}

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

// Switch between dashboard sections
function showSection(sectionId) {
  // Hide all sections
  document.querySelectorAll('.student-section').forEach(sec => {
    sec.style.display = 'none';
    sec.classList.remove('active');
  });
  
  // Show target
  const target = document.getElementById(`section-${sectionId}`);
  if (target) {
    target.style.display = 'block';
    setTimeout(() => target.classList.add('active'), 50);
  }
  
  // Update sidebar nav highlighting
  document.querySelectorAll('.sidebar-nav a').forEach(a => a.classList.remove('active'));
  const activeNav = document.getElementById(`nav-${sectionId}`);
  if (activeNav) activeNav.classList.add('active');
  
  // Special title headers
  const titles = {
    overview: 'Welcome Back!',
    marks: 'My Internal Assessment Marks',
    attendance: 'Detailed Attendance Logs',
    notifications: 'My Notifications & Alert Feed'
  };
  document.getElementById('topbar-dashboard-title').textContent = titles[sectionId] || 'Student Portal';
}

// Populate student profile fields
function loadStudentProfile() {
  document.getElementById('banner-student-name').textContent = studentData.name;
  document.getElementById('banner-student-roll').textContent = studentData.roll_number;
  document.getElementById('banner-student-dept').textContent = studentData.department;
  document.getElementById('banner-student-sem').textContent = `Semester ${studentData.semester || 1}`;
  
  document.getElementById('standing-email').textContent = studentData.email || 'None';
  document.getElementById('standing-alt-email').textContent = studentData.alt_email || 'None';
  document.getElementById('standing-phone').textContent = studentData.phone || 'None';
  document.getElementById('standing-alt-phone').textContent = studentData.alt_phone || 'None';
  document.getElementById('standing-year').textContent = studentData.year_of_admission || 'N/A';
}

// Fetch cumulative attendance stats
async function loadStudentStats() {
  try {
    const res = await fetch(`${API}/api/attendance/percentage/${studentData.id}`);
    const data = await res.json();
    
    const pct = data.attendance_percentage;
    document.getElementById('stat-attendance-pct').textContent = `${pct.toFixed(1)}%`;
    document.getElementById('stat-total-present').textContent = data.total_present || 0;
    document.getElementById('stat-total-absent').textContent = data.total_absent || 0;
    
    // Status color badge
    const badge = document.getElementById('standing-attendance-badge');
    if (pct >= 75) {
      badge.className = 'badge badge-success';
      badge.textContent = 'Good Standing (>=75%)';
    } else if (pct >= 50) {
      badge.className = 'badge badge-orange';
      badge.textContent = 'Attendance Low (<75%)';
    } else {
      badge.className = 'badge badge-danger';
      badge.textContent = 'Critical Alert (<50%)';
    }
    
  } catch (err) {
    console.error(err);
    toast('❌ Error loading attendance stats.', 'error');
  }
}

// Fetch notifications feed
async function loadStudentNotifications() {
  try {
    const res = await fetch(`${API}/api/notifications?student_id=${studentData.id}`);
    const notifications = await res.json();
    
    // Overview widget
    const recentContainer = document.getElementById('recent-notifs-container');
    recentContainer.innerHTML = '';
    
    // Full log widget
    const fullContainer = document.getElementById('student-notifs-full-container');
    fullContainer.innerHTML = '';
    
    if (notifications.length === 0) {
      recentContainer.innerHTML = `
        <div style="text-align: center; padding: 30px; color: var(--text-muted);">
          No recent notifications.
        </div>
      `;
      fullContainer.innerHTML = `
        <div style="text-align: center; padding: 50px; color: var(--text-muted);">
          You have no notifications.
        </div>
      `;
      return;
    }
    
    // Populate Overview
    const recent = notifications.slice(0, 3);
    recent.forEach(n => {
      const item = document.createElement('div');
      item.style.padding = '12px 14px';
      item.style.background = 'rgba(255,255,255,0.01)';
      item.style.borderBottom = '1px solid var(--border)';
      item.style.fontSize = '13px';
      item.innerHTML = `
        <div style="display:flex; justify-content:space-between; margin-bottom: 4px;">
          <span style="font-weight:700; color:var(--purple);">${n.type.toUpperCase().replace('_', ' ')}</span>
          <span style="font-size:11px; color:var(--text-muted);">${new Date(n.sent_at).toLocaleDateString()}</span>
        </div>
        <p style="margin:0; color:var(--text-secondary);">${n.message}</p>
      `;
      recentContainer.appendChild(item);
    });
    
    // Populate Full Feed
    notifications.forEach(n => {
      let badgeClass = 'badge-purple';
      if (n.type === 'absence') badgeClass = 'badge-danger';
      else if (n.type === 'low_attendance') badgeClass = 'badge-orange';
      else if (n.type === 'marks_published') badgeClass = 'badge-success';
      
      const div = document.createElement('div');
      div.style.padding = '18px';
      div.style.background = 'rgba(255,255,255,0.02)';
      div.style.border = '1px solid var(--border)';
      div.style.borderRadius = 'var(--radius-sm)';
      div.style.marginBottom = '12px';
      div.innerHTML = `
        <div style="display:flex; justify-content:space-between; margin-bottom: 8px;">
          <span class="badge ${badgeClass}">${n.type.toUpperCase().replace('_', ' ')}</span>
          <span style="font-size:11px; color:var(--text-muted);">${new Date(n.sent_at).toLocaleString()}</span>
        </div>
        <div style="font-size: 14px; color: var(--text-primary); line-height: 1.5;">
          ${n.message}
        </div>
      `;
      fullContainer.appendChild(div);
    });
    
  } catch (err) {
    console.error(err);
  }
}

// Fetch internal marks
async function loadStudentMarks() {
  try {
    const res = await fetch(`${API}/api/marks/${studentData.id}`);
    const data = await res.json();
    
    const tbody = document.getElementById('student-marks-tbody');
    tbody.innerHTML = '';
    
    const marks = data.marks || [];
    
    if (marks.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" style="text-align: center; color: var(--text-muted);">
            No internal marks released yet.
          </td>
        </tr>
      `;
      document.getElementById('stat-gpa').textContent = '0';
      return;
    }
    
    document.getElementById('stat-gpa').textContent = marks.length;
    
    marks.forEach(m => {
      const pct = m.max_marks > 0 ? (m.obtained_marks / m.max_marks * 100) : 0;
      const isPass = pct >= 40;
      
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${m.subject_code || 'CS'}</strong></td>
        <td>${m.subject_name || 'Subject'}</td>
        <td>${m.exam_type}</td>
        <td><strong>${m.obtained_marks.toFixed(1)}</strong></td>
        <td>${m.max_marks.toFixed(0)}</td>
        <td>
          <span style="font-weight: 800; color: ${isPass ? 'var(--green)' : 'var(--red)'};">
            ${pct.toFixed(1)}%
          </span>
        </td>
        <td>
          <span class="badge ${isPass ? 'badge-success' : 'badge-danger'}">
            ${isPass ? 'Pass' : 'Fail'}
          </span>
        </td>
        <td style="color: var(--text-secondary); font-style: italic;">
          ${m.remarks || 'No remarks'}
        </td>
      `;
      tbody.appendChild(tr);
    });
    
  } catch (err) {
    console.error(err);
  }
}

// Fetch detailed attendance log
async function loadStudentAttendanceLogs() {
  try {
    const res = await fetch(`${API}/api/attendance/records?student_id=${studentData.id}`);
    const logs = await res.json();
    
    const tbody = document.getElementById('student-attendance-tbody');
    tbody.innerHTML = '';
    
    if (logs.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; color: var(--text-muted);">
            No attendance records found.
          </td>
        </tr>
      `;
      return;
    }
    
    logs.forEach(l => {
      const isPresent = l.status === 'Present';
      
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${l.date}</strong></td>
        <td>${l.subject}</td>
        <td>Lecture</td>
        <td>Class Session Check-in</td>
        <td>${l.time}</td>
        <td>${isPresent ? 'QR Scan + Face Match' : 'System Auto Absent'}</td>
        <td>
          <span class="badge ${isPresent ? 'badge-success' : 'badge-danger'}">
            ${l.status}
          </span>
        </td>
      `;
      tbody.appendChild(tr);
    });
    
  } catch (err) {
    console.error(err);
  }
}

// Profile update modal controls
function openProfileModal() {
  document.getElementById('edit-email').value = studentData.email || '';
  document.getElementById('edit-alt-email').value = studentData.alt_email || '';
  document.getElementById('edit-phone').value = studentData.phone || '';
  document.getElementById('edit-alt-phone').value = studentData.alt_phone || '';
  document.getElementById('profile-modal').style.display = 'flex';
}

function closeProfileModal() {
  document.getElementById('profile-modal').style.display = 'none';
}

async function saveProfileSettings() {
  const emailInput = document.getElementById('edit-email').value.trim();
  const altEmailInput = document.getElementById('edit-alt-email').value.trim();
  const phoneInput = document.getElementById('edit-phone').value.trim();
  const altPhoneInput = document.getElementById('edit-alt-phone').value.trim();
  
  // Simple validation
  if (emailInput && !emailInput.includes('@')) {
    toast('❌ Please enter a valid primary email address.', 'error');
    return;
  }
  if (altEmailInput && !altEmailInput.includes('@')) {
    toast('❌ Please enter a valid alternative email address.', 'error');
    return;
  }
  
  try {
    const res = await fetch(`${API}/api/students/${studentData.id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        email: emailInput || null,
        alt_email: altEmailInput || null,
        phone: phoneInput || null,
        alt_phone: altPhoneInput || null
      })
    });
    
    const result = await res.json();
    if (res.ok && result.success) {
      // Update local storage and local variable
      studentData.email = result.student.email;
      studentData.alt_email = result.student.alt_email;
      studentData.phone = result.student.phone;
      studentData.alt_phone = result.student.alt_phone;
      localStorage.setItem('user_data', JSON.stringify(studentData));
      
      // Update UI elements
      loadStudentProfile();
      
      toast('✅ Profile settings updated successfully!', 'success');
      closeProfileModal();
    } else {
      toast(`❌ Error updating settings: ${result.error || 'Unknown error'}`, 'error');
    }
  } catch (err) {
    console.error(err);
    toast('❌ Network error updating profile settings.', 'error');
  }
}
