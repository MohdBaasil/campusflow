/**
 * login.js — Multi-role Login & Student Registration Wizard
 * Handles Staff/Student tabs, login, 4-step registration wizard with 5-angle face capture.
 */

const API = window.location.protocol === 'file:' ? 'http://127.0.0.1:5000' : '';

// ─── Tab Switching ───────────────────────────────
function switchTab(tab) {
  document.querySelectorAll('.login-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.getElementById(`tab-${tab}`).classList.add('active');
  document.getElementById(`pane-${tab}`).classList.add('active');
  clearAlert();
  stopRegCamera();
  stopStuLoginCamera();
  if (tab === 'student') {
    switchStudentView('login');
  }
  
}

function switchStudentView(view) {
  clearAlert();
  document.getElementById('sub-login').classList.toggle('active', view === 'login');
  document.getElementById('sub-register').classList.toggle('active', view === 'register');
  document.getElementById('student-login-view').style.display = view === 'login' ? 'block' : 'none';
  document.getElementById('student-register-view').style.display = view === 'register' ? 'block' : 'none';

  if (view === 'register') {
    // Reset wizard to step 1
    currentWizStep = 1;
    currentPose = 0;
    capturedFaces = [null, null, null, null, null];
    docFiles = { marksheet: null, idcard: null };
    updateWizardUI();
    stopRegCamera();
    stopStuLoginCamera();
  } else {
    stopRegCamera();
    switchStudentLoginMode('password');
  }
}


// ─── Alerts & Toasts ─────────────────────────────
function showAlert(msg, type = 'error') {
  document.getElementById('login-alert').innerHTML =
    `<div class="alert alert-${type}" style="margin-bottom:16px;">${msg}</div>`;
}
function clearAlert() {
  document.getElementById('login-alert').innerHTML = '';
}
function toast(msg, type = 'info') {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  t.innerHTML = `<span>${icons[type] || ''}</span><span>${msg}</span>`;
  c.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 3500);
}


// ─── Staff Login ─────────────────────────────────
async function staffLogin() {
  const username = document.getElementById('staff-user').value.trim();
  const password = document.getElementById('staff-pass').value;

  if (!username || !password) {
    showAlert('⚠️ Please enter both username and password.', 'warning');
    return;
  }

  const btn = document.getElementById('staff-login-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Logging in...';

  try {
    const res = await fetch(`${API}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'staff', username, password })
    });
    const data = await res.json();

    if (data.success) {
      localStorage.setItem('session_token', data.token);
      localStorage.setItem('user_type', data.user_type);
      localStorage.setItem('user_data', JSON.stringify(data.user_data));
      toast('✅ Login successful! Redirecting...', 'success');
      const urlParams = new URLSearchParams(window.location.search);
      const redirectUrl = urlParams.get('redirect');
      setTimeout(() => { window.location.href = redirectUrl ? decodeURIComponent(redirectUrl) : 'index.html'; }, 600);
    } else {
      showAlert(`❌ ${data.error}`, 'error');
    }
  } catch (err) {
    showAlert('❌ Cannot connect to server. Make sure the backend is running.', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '🔐 Login as Staff';
  }
}


// ─── Student Login Modes & Camera ────────────────
let stuLoginStream = null;
let uploadedStuLoginImageData = null;

function switchStudentLoginMode(mode) {
  clearAlert();
  const faceBtn = document.getElementById('btn-stu-face-login');
  const passBtn = document.getElementById('btn-stu-pass-login');
  const facePane = document.getElementById('stu-face-login-pane');
  const passPane = document.getElementById('stu-pass-login-pane');
  
  if (mode === 'face') {
    faceBtn.classList.add('active');
    passBtn.classList.remove('active');
    facePane.style.display = 'block';
    passPane.style.display = 'none';
    startStuLoginCamera();
  } else {
    passBtn.classList.add('active');
    faceBtn.classList.remove('active');
    facePane.style.display = 'none';
    passPane.style.display = 'block';
    stopStuLoginCamera();
  }
}

function handleStuLoginFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = function(e) {
    uploadedStuLoginImageData = e.target.result;

    // Stop camera streaming and hide video
    stopStuLoginCamera();

    const video = document.getElementById('stu-login-video');
    const preview = document.getElementById('stu-login-uploaded-preview');
    const camBox = document.getElementById('stu-login-cam-box');
    
    if (camBox) camBox.style.display = 'block';
    if (video) video.style.display = 'none';
    if (preview) {
      preview.src = uploadedStuLoginImageData;
      preview.style.display = 'block';
    }

    document.getElementById('stu-login-cam-status').textContent = '📁 Photo Uploaded: ' + file.name;
    toast('📷 Photo file loaded! Click Scan Face & Login to verify.', 'info');
  };
  reader.readAsDataURL(file);
}

async function startStuLoginCamera() {
  uploadedStuLoginImageData = null;
  const video = document.getElementById('stu-login-video');
  const preview = document.getElementById('stu-login-uploaded-preview');
  if (video) video.style.display = 'block';
  if (preview) {
    preview.src = '';
    preview.style.display = 'none';
  }
  if (stuLoginStream) return;
  const camBox = document.getElementById('stu-login-cam-box');
  camBox.style.display = 'block';
  
  try {
    stuLoginStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' }
    });
    video.srcObject = stuLoginStream;
    video.style.transform = 'scaleX(-1)';
    document.getElementById('stu-login-cam-status').textContent = '🟢 Camera Active';
  } catch (err) {
    console.error('Login Camera error:', err);
    showAlert('❌ Cannot access camera. Please grant camera permission.', 'error');
    document.getElementById('stu-login-cam-status').textContent = '❌ Camera Error';
  }
}

function stopStuLoginCamera() {
  if (stuLoginStream) {
    stuLoginStream.getTracks().forEach(t => t.stop());
    stuLoginStream = null;
  }
  const video = document.getElementById('stu-login-video');
  if (video) video.srcObject = null;
  const camBox = document.getElementById('stu-login-cam-box');
  if (!uploadedStuLoginImageData && camBox) camBox.style.display = 'none';
}

// ─── Student Face Login ──────────────────────────
async function studentFaceLogin() {
  clearAlert();
  const roll = document.getElementById('stu-roll').value.trim().toUpperCase();
  if (!roll) {
    showAlert('⚠️ Please enter your Roll Number first.', 'warning');
    return;
  }

  const video = document.getElementById('stu-login-video');
  const canvas = document.getElementById('stu-login-canvas');
  
  let imageData = null;
  if (uploadedStuLoginImageData) {
    imageData = uploadedStuLoginImageData;
  } else {
    if (!stuLoginStream || video.readyState < 2) {
      toast('📷 Camera not ready. Please wait...', 'warning');
      return;
    }
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0);
    imageData = canvas.toDataURL('image/jpeg', 0.85);
  }

  const btn = document.getElementById('btn-stu-face-scan');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Verifying Face...';

  try {
    const res = await fetch(`${API}/api/auth/login-face`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ roll_number: roll, image: imageData })
    });
    const data = await res.json();

    if (data.success) {
      localStorage.setItem('session_token', data.token);
      localStorage.setItem('user_type', data.user_type);
      localStorage.setItem('user_data', JSON.stringify(data.user_data));
      toast('✅ Face matched successfully!', 'success');
      stopStuLoginCamera();
      
      const urlParams = new URLSearchParams(window.location.search);
      const redirectUrl = urlParams.get('redirect');
      setTimeout(() => {
        window.location.href = redirectUrl ? decodeURIComponent(redirectUrl) : 'student_dashboard.html';
      }, 600);
    } else {
      showAlert(`❌ ${data.error}`, 'error');
    }
  } catch (err) {
    showAlert('❌ Server connection error.', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '🤳 Scan Face & Login';
  }
}

// ─── Student Password Login ──────────────────────
async function studentPasswordLogin() {
  const roll = document.getElementById('stu-roll-pass').value.trim().toUpperCase();
  const password = document.getElementById('stu-pass').value;

  if (!roll || !password) {
    showAlert('⚠️ Please enter both roll number and password.', 'warning');
    return;
  }

  try {
    const res = await fetch(`${API}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'student', roll_number: roll, password })
    });
    const data = await res.json();

    if (data.success) {
      localStorage.setItem('session_token', data.token);
      localStorage.setItem('user_type', data.user_type);
      localStorage.setItem('user_data', JSON.stringify(data.user_data));
      toast('✅ Login successful!', 'success');
      stopStuLoginCamera();
      
      const urlParams = new URLSearchParams(window.location.search);
      const redirectUrl = urlParams.get('redirect');
      setTimeout(() => {
        window.location.href = redirectUrl ? decodeURIComponent(redirectUrl) : 'student_dashboard.html';
      }, 600);
    } else {
      showAlert(`❌ ${data.error}`, 'error');
    }
  } catch (err) {
    showAlert('❌ Cannot connect to server.', 'error');
  }
}


// ═══════════════════════════════════════════════
// REGISTRATION WIZARD
// ═══════════════════════════════════════════════
let currentWizStep = 1;
let currentPose = 0;
let capturedFaces = [null, null, null, null, null];
let docFiles = { marksheet: null, idcard: null };
let regStream = null;

const POSE_INSTRUCTIONS = [
  '📷 Look straight at the camera (neutral face)',
  '😊 Look straight and smile naturally',
  '◀ Turn your head slightly to the LEFT',
  '▶ Turn your head slightly to the RIGHT',
  '⬆ Tilt your head slightly UP'
];

function updateWizardUI() {
  // Update step indicators
  for (let i = 1; i <= 4; i++) {
    const el = document.getElementById(`rs-${i}`);
    el.classList.remove('active', 'done');
    if (i < currentWizStep) el.classList.add('done');
    else if (i === currentWizStep) el.classList.add('active');
  }

  // Show active wizard step
  for (let i = 1; i <= 4; i++) {
    const wiz = document.getElementById(`wiz-${i}`);
    wiz.classList.toggle('active', i === currentWizStep);
  }

  // If step 3, start camera and update pose UI
  if (currentWizStep === 3) {
    startRegCamera();
    updatePoseUI();
  }
}

function updatePoseUI() {
  for (let i = 0; i < 5; i++) {
    const chip = document.getElementById(`pose-${i}`);
    chip.classList.remove('active', 'done');
    if (capturedFaces[i]) chip.classList.add('done');
    else if (i === currentPose) chip.classList.add('active');
  }

  const instrEl = document.getElementById('pose-instruction');
  if (currentPose < 5) {
    instrEl.textContent = POSE_INSTRUCTIONS[currentPose];
  }

  const btn = document.getElementById('capture-pose-btn');
  if (currentPose < 5) {
    btn.textContent = `📸 Capture Pose ${currentPose + 1}/5`;
    btn.disabled = false;
  } else {
    btn.textContent = '✅ All 5 Poses Captured!';
    btn.disabled = true;
  }

  const pct = (capturedFaces.filter(f => f !== null).length / 5) * 100;
  document.getElementById('face-progress').style.width = pct + '%';
}


// ─── Wizard Navigation ──────────────────────────
function wizNext(fromStep) {
  clearAlert();

  if (fromStep === 1) {
    const name = document.getElementById('reg-name').value.trim();
    const usn = document.getElementById('reg-usn').value.trim();
    const dept = document.getElementById('reg-dept').value;
    const pwd = document.getElementById('reg-pwd').value;
    const pwd2 = document.getElementById('reg-pwd2').value;

    if (!name) { showAlert('⚠️ Please enter your full name.', 'warning'); return; }
    if (!usn) { showAlert('⚠️ Please enter your USN / Roll Number.', 'warning'); return; }
    if (!dept) { showAlert('⚠️ Please select a department.', 'warning'); return; }
    if (pwd.length < 4) { showAlert('⚠️ Password must be at least 4 characters.', 'warning'); return; }
    if (pwd !== pwd2) { showAlert('⚠️ Passwords do not match.', 'warning'); return; }
  }

  if (fromStep === 2) {
    // Documents are optional, just proceed
  }

  currentWizStep = fromStep + 1;
  updateWizardUI();
}

function wizBack(fromStep) {
  clearAlert();
  if (fromStep === 3) stopRegCamera();
  currentWizStep = fromStep - 1;
  updateWizardUI();
}


// ─── Document Upload ─────────────────────────────
function onDocSelect(input, type) {
  const file = input.files[0];
  if (!file) return;

  docFiles[type] = file;
  const nameEl = document.getElementById(`dz-${type}-name`);
  const zoneEl = document.getElementById(`dz-${type}`);

  nameEl.textContent = `✅ ${file.name}`;
  zoneEl.classList.add('filled');
  toast(`📄 ${type === 'marksheet' ? 'Marksheet' : 'ID Card'} uploaded`, 'success');
}


// ─── Camera for Face Capture ─────────────────────
async function startRegCamera() {
  const video = document.getElementById('reg-video');
  try {
    regStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' }
    });
    video.srcObject = regStream;
    video.style.transform = 'scaleX(-1)';
    document.getElementById('reg-cam-status').textContent = '🟢 Camera Active';
  } catch (err) {
    console.error('Camera error:', err);
    showAlert('❌ Cannot access camera. Please grant camera permission.', 'error');
    document.getElementById('reg-cam-status').textContent = '❌ Camera Error';
  }
}

function stopRegCamera() {
  if (regStream) {
    regStream.getTracks().forEach(t => t.stop());
    regStream = null;
  }
  const video = document.getElementById('reg-video');
  if (video) video.srcObject = null;
}

function captureFrame() {
  const video = document.getElementById('reg-video');
  const canvas = document.getElementById('reg-canvas');
  if (!regStream || video.readyState < 2) return null;

  canvas.width = video.videoWidth || 640;
  canvas.height = video.videoHeight || 480;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0);
  return canvas.toDataURL('image/jpeg', 0.85);
}


// ─── Capture Pose ────────────────────────────────
async function capturePose() {
  if (currentPose >= 5) return;

  const imageData = captureFrame();
  if (!imageData) {
    toast('📷 Camera not ready. Please wait...', 'warning');
    return;
  }

  const btn = document.getElementById('capture-pose-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Processing...';

  // For pose 1 (smile), verify smile first
  if (currentPose === 1) {
    try {
      const res = await fetch(`${API}/api/auth/verify-smile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: imageData })
      });
      const data = await res.json();

      if (!data.smile_detected) {
        showAlert(`😊 ${data.message} Please smile and try again.`, 'warning');
        btn.disabled = false;
        btn.textContent = `📸 Capture Pose ${currentPose + 1}/5`;
        return;
      }
      clearAlert();
      toast('😊 Smile detected!', 'success');
    } catch (err) {
      // Soft gate — allow even if smile check fails
      console.warn('Smile verification failed, allowing capture:', err);
    }
  }

  // Store captured face
  capturedFaces[currentPose] = imageData;
  currentPose++;
  updatePoseUI();
  clearAlert();

  if (currentPose < 5) {
    toast(`✅ Pose ${currentPose}/5 captured!`, 'success');
  } else {
    toast('🎉 All 5 poses captured! Submitting registration...', 'success');
    stopRegCamera();
    await submitRegistration();
  }

  btn.disabled = false;
  if (currentPose < 5) {
    btn.textContent = `📸 Capture Pose ${currentPose + 1}/5`;
  }
}


// ─── Submit Registration ─────────────────────────
async function submitRegistration() {
  const name = document.getElementById('reg-name').value.trim();
  const usn = document.getElementById('reg-usn').value.trim().toUpperCase();
  const dept = document.getElementById('reg-dept').value;
  const pwd = document.getElementById('reg-pwd').value;

  // Build FormData
  const fd = new FormData();
  fd.append('name', name);
  fd.append('roll_number', usn);
  fd.append('department', dept);
  fd.append('password', pwd);

  // Attach face images
  for (let i = 0; i < 5; i++) {
    if (capturedFaces[i]) {
      fd.append(`face_${i}`, capturedFaces[i]);
    }
  }

  // Attach documents
  if (docFiles.marksheet) fd.append('marksheet', docFiles.marksheet);
  if (docFiles.idcard) fd.append('id_card', docFiles.idcard);

  try {
    showAlert('⏳ Registering student... This may take a few seconds.', 'info');

    const res = await fetch(`${API}/api/auth/register-portal`, {
      method: 'POST',
      body: fd
    });
    const data = await res.json();

    if (data.success) {
      // Move to step 4 (success)
      currentWizStep = 4;
      updateWizardUI();

      document.getElementById('reg-result-info').innerHTML = `
        <div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid var(--border);">
          <span style="color:var(--text-muted);">Name</span>
          <span style="color:var(--text-primary); font-weight:700;">${data.student.name}</span>
        </div>
        <div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid var(--border);">
          <span style="color:var(--text-muted);">Roll Number</span>
          <span style="color:var(--purple); font-weight:700;">${data.student.roll_number}</span>
        </div>
        <div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid var(--border);">
          <span style="color:var(--text-muted);">Department</span>
          <span style="color:var(--text-primary); font-weight:700;">${data.student.department}</span>
        </div>
        <div style="display:flex; justify-content:space-between; padding:6px 0;">
          <span style="color:var(--text-muted);">Face Photos</span>
          <span style="color:var(--green); font-weight:700;">${data.saved_faces} enrolled</span>
        </div>
      `;
      clearAlert();
      toast('🎉 Registration complete!', 'success');
    } else {
      showAlert(`❌ ${data.error}`, 'error');
    }
  } catch (err) {
    showAlert('❌ Network error. Please check your connection and try again.', 'error');
    console.error('Registration error:', err);
  }
}


// ─── Enter key support ───────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // If already logged in, redirect
  const userType = localStorage.getItem('user_type');
  const urlParams = new URLSearchParams(window.location.search);
  const redirectUrl = urlParams.get('redirect');

  if (userType === 'staff') {
    window.location.href = 'index.html';
    return;
  }
  
  if (userType === 'student') {
    window.location.href = redirectUrl ? decodeURIComponent(redirectUrl) : 'student.html';
    return;
  }

  // Enter key for staff login
  document.getElementById('staff-pass').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') staffLogin();
  });
  document.getElementById('staff-user').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') staffLogin();
  });

  // Enter key for student login
  document.getElementById('stu-pass').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') studentPasswordLogin();
  });

  
  
});
