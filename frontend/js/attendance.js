// Auth guard — redirect to login if not staff
if (localStorage.getItem("user_type") !== "staff") {
    window.location.href = "login.html";
}

/* ── Attendance JavaScript ── */
const API = window.location.protocol === 'file:' ? 'http://127.0.0.1:5000/api' : '/api';

let stream = null;
let isRunning = false;
let captureInterval = null;
let sessionPresent = new Set();
let sessionFaces = 0;
let sessionUnknown = 0;
let logEntries = [];

// ── Toast ─────────────────────────────────────
function toast(msg, type = 'info') {
  const tc = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  t.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${msg}</span>`;
  tc.appendChild(t);
  setTimeout(() => t.remove(), 4500);
}

function showAlert(msg, type = 'error') {
  document.getElementById('att-alert').innerHTML =
    `<div class="alert alert-${type}">${msg}</div>`;
}

// ── Load Subjects ─────────────────────────────
async function loadSubjects() {
  try {
    const res = await fetch(`${API}/subjects`);
    const subjects = await res.json();
    const sel = document.getElementById('subject-select');
    subjects.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s;
      opt.textContent = s;
      sel.appendChild(opt);
    });
  } catch (e) {
    showAlert('❌ Cannot connect to server. Make sure run.py is running.', 'error');
  }
}

// ── Camera Mirroring ──────────────────────────
let isMirrored = localStorage.getItem('cam_mirrored') !== 'false'; // Default to true (mirrored is standard selfie)
let currentFacingMode = 'user';

function applyMirrorState() {
  const video = document.getElementById('att-video');
  if (video) {
    video.style.transform = isMirrored ? 'scaleX(-1)' : 'none';
  }
}

async function flipCamera() {
  currentFacingMode = currentFacingMode === 'user' ? 'environment' : 'user';
  isMirrored = (currentFacingMode === 'user');
  localStorage.setItem('cam_mirrored', isMirrored);
  
  toast(currentFacingMode === 'user' ? '📷 Switched to Front Camera' : '📷 Switched to Back Camera', 'success');
  
  if (stream) {
    // If active, stop and restart stream
    const video = document.getElementById('att-video');
    if (video) video.srcObject = null;
    stream.getTracks().forEach(t => t.stop());
    stream = null;
    try {
      await startAttendance();
    } catch (e) {
      console.error('Failed to restart camera on flip:', e);
    }
  } else {
    applyMirrorState();
  }
}

// ── Start/Stop Attendance ─────────────────────
async function toggleAttendance() {
  if (isRunning) {
    stopAttendance();
  } else {
    await startAttendance();
  }
}

async function startAttendance() {
  const subject = document.getElementById('subject-select').value;
  if (!subject) {
    showAlert('⚠️ Please select a subject first.', 'warning');
    return;
  }

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: currentFacingMode }
    });

    const video = document.getElementById('att-video');
    video.srcObject = stream;
    applyMirrorState();

    isRunning = true;
    document.getElementById('start-btn').innerHTML = '⏹ Stop';
    document.getElementById('start-btn').className = 'btn btn-danger';
    document.getElementById('att-overlay').style.display = 'block';
    document.getElementById('att-cam-status').textContent = '🔴 Recording';
    document.getElementById('recognition-status').className = 'badge badge-success';
    document.getElementById('recognition-status').textContent = '▶ Active';
    document.getElementById('rec-indicator').style.display = 'inline';

    // Show scanning grid overlay (since only standard mode uses the camera)
    const faceGrid = document.getElementById('face-grid');
    const qrOverlay = document.getElementById('qr-target-overlay');
    if (qrOverlay) qrOverlay.style.display = 'none';
    if (faceGrid) faceGrid.style.display = 'block';
    captureInterval = setInterval(processFrame, 2500);

    document.getElementById('att-alert').innerHTML = '';

  } catch (err) {
    showAlert('❌ Camera access denied. Please allow camera permissions in your browser.', 'error');
  }
}

function stopAttendance() {
  clearInterval(captureInterval);
  captureInterval = null;
  isRunning = false;

  if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }

  const video = document.getElementById('att-video');
  video.srcObject = null;

  document.getElementById('att-overlay').style.display = 'none';
  document.getElementById('att-cam-status').textContent = '⏸ Stopped';
  document.getElementById('start-btn').innerHTML = '▶ Start';
  document.getElementById('start-btn').className = 'btn btn-primary';
  document.getElementById('recognition-status').className = 'badge badge-orange';
  document.getElementById('recognition-status').textContent = '⏸ Paused';
  document.getElementById('rec-indicator').style.display = 'none';

  // Hide overlays
  const faceGrid = document.getElementById('face-grid');
  if (faceGrid) faceGrid.style.display = 'none';
  const qrOverlay = document.getElementById('qr-target-overlay');
  if (qrOverlay) qrOverlay.style.display = 'none';

  // Hide annotated overlay
  const annotated = document.getElementById('att-annotated');
  if (annotated) annotated.style.display = 'none';
  video.style.opacity = '1';

  toast(`Session ended. ${sessionPresent.size} student(s) marked present.`, 'info');
}

// ── Capture and Process Frame ─────────────────
async function processFrame() {
  if (!isRunning || !stream) return;

  const video = document.getElementById('att-video');
  if (video.readyState < 2) return;

  const canvas = document.getElementById('att-canvas');
  canvas.width = video.videoWidth || 640;
  canvas.height = video.videoHeight || 480;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0);
  const imageData = canvas.toDataURL('image/jpeg', 0.85);

  const subject = document.getElementById('subject-select').value;
  const mode = document.getElementById('mode-select').value;

  try {
    const res = await fetch(`${API}/attendance/capture`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: imageData, subject })
    });
    const data = await res.json();

    if (!res.ok) {
      if (data.error && data.error.includes('not trained')) {
        showAlert('⚠️ Model not trained yet. Go to Dashboard → Train Model first.', 'warning');
        stopAttendance();
      }
      return;
    }

    // Update annotated image overlay
    if (data.annotated_image) {
      const annotated = document.getElementById('att-annotated');
      annotated.src = data.annotated_image;
      annotated.style.display = 'block';
      video.style.opacity = '0.3';
      setTimeout(() => {
        annotated.style.display = 'none';
        video.style.opacity = '1';
      }, 2000);
    }

    sessionFaces += data.faces_detected;
    document.getElementById('sess-faces').textContent = sessionFaces;

    data.results.forEach(r => {
      if (r.recognized && !r.already_marked) {
        sessionPresent.add(r.student_id);
        addLogEntry(r);
        toast(`✅ ${r.name} marked present (${r.confidence}%)`, 'success');
      } else if (r.recognized && r.already_marked) {
        // Already marked, no toast spam
      } else {
        sessionUnknown++;
        document.getElementById('sess-unknown').textContent = sessionUnknown;
      }
    });

    document.getElementById('sess-present').textContent = sessionPresent.size;

  } catch (e) {
    console.error('Frame processing error:', e);
  }
}

let isSessionActive = false;
let sessionPollInterval = null;

// ── Mode Switcher ──────────────────────────────
function switchAttendanceMode() {
  const mode = document.getElementById('mode-select').value;
  const subtitle = document.getElementById('att-subtitle');
  const qrOverlay = document.getElementById('qr-target-overlay');
  const faceGrid = document.getElementById('face-grid');
  
  const cameraCard = document.getElementById('camera-card');
  const sessionQRCard = document.getElementById('session-qr-card');

  // Stop any active camera attendance
  if (isRunning) {
    stopAttendance();
  }
  // Stop any active session polling
  if (isSessionActive) {
    stopSession();
  }

  if (mode === 'session') {
    subtitle.textContent = 'Daily Session QR Mode – Teachers generate a dynamic QR Code for student check-in';
    cameraCard.style.display = 'none';
    sessionQRCard.style.display = 'block';
  } else {
    cameraCard.style.display = 'block';
    sessionQRCard.style.display = 'none';

    subtitle.textContent = 'Live ArcFace face recognition – scans every 2.5 seconds';
    if (qrOverlay) qrOverlay.style.display = 'none';
    if (isRunning) {
      if (faceGrid) faceGrid.style.display = 'block';
      clearInterval(captureInterval);
      captureInterval = setInterval(processFrame, 2500);
    }
  }
}

// ── Daily QR Session Management ────────────────
async function toggleSession() {
  if (isSessionActive) {
    stopSession();
  } else {
    await startSession();
  }
}

async function startSession() {
  const subject = document.getElementById('subject-select').value;
  if (!subject) {
    showAlert('⚠️ Please select a subject first.', 'warning');
    return;
  }

  const btn = document.getElementById('session-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Starting...';

  try {
    const res = await fetch(`${API}/session/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subject })
    });
    const data = await res.json();

    if (res.ok && data.success) {
      isSessionActive = true;
      btn.textContent = '⏹ Stop Session';
      btn.className = 'btn btn-danger';
      btn.disabled = false;

      // Update QR display
      document.getElementById('session-qr-placeholder').style.display = 'none';
      document.getElementById('session-qr-display').style.display = 'block';
      document.getElementById('session-qr-img').src = data.qr_code;
      
      const link = document.getElementById('session-link');
      link.href = data.url;
      link.textContent = data.url;

      toast(`Session started for ${subject}`, 'success');
      document.getElementById('att-alert').innerHTML = '';

      // Clear the log and stats
      clearLog();
      
      // Start polling
      sessionPollInterval = setInterval(pollSessionStatus, 2000);
    } else {
      showAlert(`❌ ${data.error || 'Failed to start session'}`, 'error');
      btn.textContent = '▶ Start Session';
      btn.className = 'btn btn-primary';
      btn.disabled = false;
    }
  } catch (e) {
    showAlert('❌ Server error connecting to start session.', 'error');
    btn.textContent = '▶ Start Session';
    btn.className = 'btn btn-primary';
    btn.disabled = false;
  }
}

function stopSession() {
  clearInterval(sessionPollInterval);
  sessionPollInterval = null;
  isSessionActive = false;

  const btn = document.getElementById('session-btn');
  btn.textContent = '▶ Start Session';
  btn.className = 'btn btn-primary';

  document.getElementById('session-qr-placeholder').style.display = 'flex';
  document.getElementById('session-qr-display').style.display = 'none';
  document.getElementById('session-qr-img').src = '';
  document.getElementById('session-link').href = '';
  document.getElementById('session-link').textContent = '';

  toast('Session stopped.', 'info');
}

async function pollSessionStatus() {
  if (!isSessionActive) return;
  const subject = document.getElementById('subject-select').value;
  if (!subject) return;

  try {
    const res = await fetch(`${API}/session/status?subject=${encodeURIComponent(subject)}`);
    const data = await res.json();

    if (res.ok && data.active) {
      // Update present count
      document.getElementById('sess-present').textContent = data.count;
      document.getElementById('sess-faces').textContent = data.count;

      // Update logs in real time
      const log = document.getElementById('att-log');
      if (data.present.length === 0) {
        log.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">🔍</div>
            <div class="empty-title">Waiting for check-ins...</div>
            <div class="empty-sub">Display the QR code. Checked-in students will appear here.</div>
          </div>`;
        document.getElementById('log-count').textContent = '0 entries';
        return;
      }

      log.innerHTML = data.present.map(p => {
        const initials = p.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
        return `
          <div class="log-item">
            <div class="log-avatar">${initials}</div>
            <div class="log-info">
              <div class="log-name">${p.name}</div>
              <div class="log-detail">${p.roll_number} · ${p.department}</div>
            </div>
            <div style="display:flex; flex-direction:column; align-items:flex-end; gap:4px;">
              <span class="badge badge-success">✓ Present</span>
              <span class="log-time">${p.time}</span>
            </div>
          </div>`;
      }).join('');

      document.getElementById('log-count').textContent = `${data.present.length} entries`;
    }
  } catch (e) {
    console.error('Error polling session status:', e);
  }
}

// ── Log Entry ─────────────────────────────────
function addLogEntry(result) {
  const log = document.getElementById('att-log');
  if (log.querySelector('.empty-state')) log.innerHTML = '';

  const now = new Date().toLocaleTimeString('en-IN', { hour12: false });
  const initials = result.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();

  const item = document.createElement('div');
  item.className = 'log-item';
  item.innerHTML = `
    <div class="log-avatar">${initials}</div>
    <div class="log-info">
      <div class="log-name">${result.name}</div>
      <div class="log-detail">${result.roll_number} · ${result.department} · <em>${result.subject}</em></div>
      <div class="conf-bar" style="margin-top:6px;">
        <div class="conf-bar-fill" style="width:${result.confidence}%;"></div>
      </div>
    </div>
    <div style="display:flex; flex-direction:column; align-items:flex-end; gap:4px;">
      <span class="badge badge-success">✓ Present</span>
      <span class="log-time">${now}</span>
      <span style="font-size:10px; color:var(--cyan); font-weight:700;">${result.confidence}%</span>
    </div>
  `;
  log.insertBefore(item, log.firstChild);

  logEntries.push(result);
  document.getElementById('log-count').textContent = `${logEntries.length} entries`;
}

function clearLog() {
  logEntries = [];
  sessionPresent.clear();
  sessionFaces = 0;
  sessionUnknown = 0;
  document.getElementById('att-log').innerHTML = `
    <div class="empty-state">
      <div class="empty-icon">🔍</div>
      <div class="empty-title">Waiting for faces...</div>
      <div class="empty-sub">Start the camera and select a subject to begin recognition.</div>
    </div>`;
  document.getElementById('sess-present').textContent = '0';
  document.getElementById('sess-faces').textContent = '0';
  document.getElementById('sess-unknown').textContent = '0';
  document.getElementById('log-count').textContent = '0 entries';
}

// ── Init ──────────────────────────────────────
loadSubjects();
