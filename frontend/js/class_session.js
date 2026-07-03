/**
 * class_session.js
 * Controls the active live class session, student QR generation, polling check-ins, and manual override lists.
 */

const API = window.location.protocol === 'file:' ? 'http://127.0.0.1:5000' : '';
const urlParams = new URLSearchParams(window.location.search);
const sessionId = urlParams.get('session_id');

let sessionData = null;
let allStudents = [];
let presentStudentsSet = new Set(); // student IDs marked present
let pollInterval = null;
let timerInterval = null;

document.addEventListener('DOMContentLoaded', () => {
  if (!sessionId) {
    toast('❌ No active session ID provided.', 'error');
    setTimeout(() => { window.location.href = 'index.html'; }, 2000);
    return;
  }
  
  initSession();
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

// Initialise the session room
async function initSession() {
  await fetchSessionDetails();
  await loadClassStudents();
  
  // Start Polling and Timer
  pollInterval = setInterval(pollCheckins, 3000);
  startTimer();
}

// Fetch details for the session
async function fetchSessionDetails() {
  try {
    const res = await fetch(`${API}/api/class-sessions/${sessionId}`);
    if (!res.ok) throw new Error('Failed to load session info');
    sessionData = await res.json();
    
    // Check if session is already completed
    if (sessionData.status === 'completed') {
      toast('ℹ️ This class session is already completed.', 'info');
      document.getElementById('btn-end-session').disabled = true;
      document.getElementById('btn-end-session').textContent = '✅ Session Completed';
      clearInterval(pollInterval);
      clearInterval(timerInterval);
      setTimeout(() => {
        window.location.href = 'index.html';
      }, 3000);
    }
    
    // Set headers
    document.getElementById('session-header-title').textContent = `${sessionData.subject_code} — ${sessionData.subject_name}`;
    document.getElementById('session-header-subtitle').textContent = `${sessionData.session_type} session on ${sessionData.date}`;
    
    // Set metadata card
    document.getElementById('meta-subject-code').textContent = sessionData.subject_code;
    document.getElementById('meta-topic').textContent = sessionData.topic_covered || 'Not specified';
    document.getElementById('meta-type').textContent = sessionData.session_type;
    document.getElementById('meta-start-time').textContent = sessionData.start_time;
    
    // Render QR Code
    if (sessionData.qr_code && sessionData.status === 'active') {
      document.getElementById('qr-code-img').src = sessionData.qr_code;
      document.getElementById('qr-code-url-text').textContent = sessionData.url;
      const timerBadge = document.getElementById('qr-code-timer-badge');
      if (timerBadge && sessionData.qr_number && sessionData.time_remaining !== undefined) {
        timerBadge.style.display = 'inline-block';
        timerBadge.textContent = `QR Code #${sessionData.qr_number}/2 — ${sessionData.time_remaining}s remaining`;
      }
    } else {
      document.getElementById('qr-code-img').src = '';
      document.getElementById('qr-code-url-text').textContent = 'QR Code not available (Active token expired).';
      const timerBadge = document.getElementById('qr-code-timer-badge');
      if (timerBadge) timerBadge.style.display = 'none';
    }
    
    // Sync present students set
    presentStudentsSet.clear();
    if (sessionData.attendance) {
      sessionData.attendance.forEach(rec => {
        if (rec.status === 'Present') {
          presentStudentsSet.add(rec.student_id);
        }
      });
    }
    
  } catch (err) {
    console.error(err);
    toast('❌ Error loading session details.', 'error');
  }
}

// Load all students in the class/department
async function loadClassStudents() {
  if (!sessionData) return;
  try {
    const res = await fetch(`${API}/api/students`);
    const students = await res.json();
    
    // Filter to department and semester (if matching)
    allStudents = students.filter(s => {
      // Allow soft match: if student has same department
      return s.department === sessionData.department;
    });
    
    // If no department matching, fall back to all students to avoid empty list
    if (allStudents.length === 0) {
      allStudents = students;
    }
    
    renderStudentChecklist();
  } catch (err) {
    console.error(err);
    toast('❌ Error loading student checklist.', 'error');
  }
}

// Render the checklist of students
function renderStudentChecklist() {
  const container = document.getElementById('student-list-container');
  const query = document.getElementById('search-student').value.toLowerCase().trim();
  
  // Save current scroll position
  const scrollPos = container.scrollTop;
  
  container.innerHTML = '';
  
  let presentCount = 0;
  
  const filtered = allStudents.filter(s => {
    return !query || s.name.toLowerCase().includes(query) || s.roll_number.toLowerCase().includes(query);
  });
  
  filtered.forEach(s => {
    const isPresent = presentStudentsSet.has(s.id);
    if (isPresent) presentCount++;
    
    // Find attendance record for details
    const rec = (sessionData.attendance || []).find(r => r.student_id === s.id && r.status === 'Present');
    const metaStr = isPresent 
      ? `✅ Present (Matched at ${rec ? rec.time : 'Check-in'})`
      : `⏳ Pending check-in`;
      
    const div = document.createElement('div');
    div.className = `student-item ${isPresent ? 'present' : ''}`;
    div.innerHTML = `
      <div class="student-info">
        <span class="student-name">${s.name}</span>
        <span class="student-meta">${s.roll_number} | ${s.department}</span>
        <span class="student-meta" style="color: ${isPresent ? 'var(--green)' : 'var(--text-muted)'}; font-weight: 600; margin-top: 4px;">
          ${metaStr}
        </span>
      </div>
      <div class="student-actions">
        <label class="form-label" style="margin: 0; display: inline-flex; align-items: center; gap: 6px; cursor: pointer;">
          <input type="checkbox" ${isPresent ? 'checked' : ''} onchange="toggleManualAttendance(this, ${s.id})" style="transform: scale(1.2); cursor: pointer;" />
          <span style="font-size: 12px; font-weight: 700; color: ${isPresent ? 'var(--green)' : 'var(--text-secondary)'};">
            ${isPresent ? 'Present' : 'Absent'}
          </span>
        </label>
      </div>
    `;
    container.appendChild(div);
  });
  
  document.getElementById('present-count').textContent = presentCount;
  document.getElementById('total-count').textContent = allStudents.length;
  
  // Restore scroll position
  container.scrollTop = scrollPos;
}

// Search filter
function filterStudents() {
  renderStudentChecklist();
}

// Poll active check-ins
async function pollCheckins() {
  if (sessionData && sessionData.status === 'completed') {
    clearInterval(pollInterval);
    return;
  }
  
  try {
    const res = await fetch(`${API}/api/class-sessions/${sessionId}`);
    const data = await res.json();
    
    // Check if session status has become completed on backend
    if (data.status === 'completed') {
      clearInterval(pollInterval);
      clearInterval(timerInterval);
      alert(`🎉 Session ended automatically!\n\nAll unmarked students have been marked as absent and notified.`);
      window.location.href = 'index.html';
      return;
    }
    
    // Check if new attendance records are found
    const oldSize = presentStudentsSet.size;
    
    presentStudentsSet.clear();
    sessionData.attendance = data.attendance || [];
    sessionData.attendance.forEach(rec => {
      if (rec.status === 'Present') {
        presentStudentsSet.add(rec.student_id);
      }
    });
    
    // Sync other session data fields to update the QR code timer
    sessionData.qr_code = data.qr_code;
    sessionData.url = data.url;
    sessionData.qr_number = data.qr_number;
    sessionData.time_remaining = data.time_remaining;
    sessionData.status = data.status;
    
    // Update QR Code visual representation
    if (sessionData.qr_code && sessionData.status === 'active') {
      document.getElementById('qr-code-img').src = sessionData.qr_code;
      document.getElementById('qr-code-url-text').textContent = sessionData.url;
      const timerBadge = document.getElementById('qr-code-timer-badge');
      if (timerBadge && sessionData.qr_number && sessionData.time_remaining !== undefined) {
        timerBadge.style.display = 'inline-block';
        timerBadge.textContent = `QR Code #${sessionData.qr_number}/2 — ${sessionData.time_remaining}s remaining`;
      }
    } else {
      document.getElementById('qr-code-img').src = '';
      document.getElementById('qr-code-url-text').textContent = 'QR Code not available (Active token expired).';
      const timerBadge = document.getElementById('qr-code-timer-badge');
      if (timerBadge) timerBadge.style.display = 'none';
    }
    
    if (presentStudentsSet.size !== oldSize) {
      toast('🔔 New student checked in!', 'success');
    }
    
    renderStudentChecklist();
  } catch (err) {
    console.warn('Polling check-ins failed:', err);
  }
}

// Toggle manual checkin checkbox
async function toggleManualAttendance(checkbox, studentId) {
  const markPresent = checkbox.checked;
  
  try {
    const payload = {
      present_student_ids: markPresent ? [studentId] : [],
      absent_student_ids: markPresent ? [] : [studentId]
    };
    
    const res = await fetch(`${API}/api/class-sessions/${sessionId}/mark-attendance`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    
    if (data.success) {
      if (markPresent) {
        presentStudentsSet.add(studentId);
        toast('✅ Student marked present manually.', 'success');
      } else {
        presentStudentsSet.delete(studentId);
        toast('ℹ️ Student marked absent/pending.', 'info');
      }
      
      // Update local session records to match
      await fetchSessionDetails();
      renderStudentChecklist();
    } else {
      checkbox.checked = !markPresent;
      toast(`❌ Error: ${data.error}`, 'error');
    }
  } catch (err) {
    checkbox.checked = !markPresent;
    console.error(err);
    toast('❌ Network error marking attendance.', 'error');
  }
}

// Timer clock
function startTimer() {
  if (!sessionData) return;
  const startParts = sessionData.start_time.split(':');
  const startDate = new Date();
  startDate.setHours(parseInt(startParts[0]), parseInt(startParts[1]), 0);
  
  const timerEl = document.getElementById('session-timer');
  
  timerInterval = setInterval(() => {
    const diff = new Date() - startDate;
    if (diff < 0) {
      timerEl.textContent = '00:00:00';
      return;
    }
    
    const secs = Math.floor((diff / 1000) % 60);
    const mins = Math.floor((diff / (1000 * 60)) % 60);
    const hrs = Math.floor((diff / (1000 * 60 * 60)) % 24);
    
    timerEl.textContent = 
      `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }, 1000);
}

// End session prompt
function promptEndSession() {
  const confirmEnd = confirm(
    'Are you sure you want to end this class session?\n\n' +
    'This will close student portal check-ins, mark all remaining unmarked students as absent (-3% penalty), and compile the final attendance percentages.'
  );
  
  if (confirmEnd) {
    endSession();
  }
}

// Call end session API
async function endSession() {
  clearInterval(pollInterval);
  clearInterval(timerInterval);
  
  const btn = document.getElementById('btn-end-session');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Compiling...';
  
  try {
    const res = await fetch(`${API}/api/class-sessions/${sessionId}/end`, {
      method: 'POST'
    });
    const data = await res.json();
    
    if (data.success) {
      alert(`🎉 Session closed successfully!\n\n${data.message}`);
      window.location.href = 'index.html';
    } else {
      toast(`❌ Error: ${data.error}`, 'error');
      btn.disabled = false;
      btn.innerHTML = '🛑 End Session & Compile';
      // Restart polling
      pollInterval = setInterval(pollCheckins, 3000);
    }
  } catch (err) {
    console.error(err);
    toast('❌ Network error ending session.', 'error');
    btn.disabled = false;
    btn.innerHTML = '🛑 End Session & Compile';
  }
}
