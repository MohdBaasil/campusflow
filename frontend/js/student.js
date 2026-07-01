// ── Student Controller ──
const API = window.location.protocol === 'file:' ? 'http://127.0.0.1:5000/api' : '/api';

// Parse query parameters
const urlParams = new URLSearchParams(window.location.search);
const token = urlParams.get('token');
const subject = urlParams.get('subject');

let stream = null;
let isMirrored = true; // Front cameras are mirrored by default for standard selfies

// Toast helper
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
  document.getElementById('student-alert').innerHTML =
    `<div class="alert alert-${type}">${msg}</div>`;
}

function clearAlert() {
  document.getElementById('student-alert').innerHTML = '';
}

// Navigation between views
function showScreen(screenId) {
  document.querySelectorAll('.screen-view').forEach(s => {
    s.classList.remove('active');
  });
  const activeScreen = document.getElementById(screenId);
  if (activeScreen) {
    activeScreen.classList.add('active');
  }
}

// Initialization and validation on page load
window.addEventListener('DOMContentLoaded', () => {
  // Prevent check-in if not authenticated as student
  if (localStorage.getItem('user_type') !== 'student') {
    window.location.href = 'login.html?redirect=' + encodeURIComponent(window.location.href);
    return;
  }

  if (!token || !subject) {
    showScreen('screen-invalid-link');
    return;
  }
  
  // Set subject badge
  document.getElementById('subject-display').textContent = `Subject: ${decodeURIComponent(subject)}`;

  // Auto-fill student roll number if logged in as student and check-in
  try {
    const userData = JSON.parse(localStorage.getItem('user_data') || '{}');
    if (userData.roll_number) {
      showScreen('screen-checking');
      autoMarkAttendance(token, subject, userData.roll_number);
    } else {
      showScreen('screen-login');
      showAlert('❌ Logged in student data not found. Please log in again.', 'error');
    }
  } catch (e) {
    console.error('Error parsing student user_data:', e);
    showScreen('screen-login');
    showAlert('❌ Error loading profile.', 'error');
  }
});

async function autoMarkAttendance(sessionToken, classSubject, rollNumber) {
  try {
    const response = await fetch(`${API}/attendance/student/session-checkin`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        roll_number: rollNumber,
        token: sessionToken,
        subject: classSubject
      })
    });

    const data = await response.json();

    if (response.ok && data.verified) {
      // Success screen
      document.getElementById('success-name').textContent = data.student.name;
      document.getElementById('success-roll').textContent = data.student.roll_number;
      document.getElementById('success-subject').textContent = data.subject;
      document.getElementById('success-time').textContent = data.time;
      document.getElementById('success-confidence').textContent = `Authenticated (Face Login)`;
      
      if (data.already_marked) {
        document.getElementById('success-confidence').textContent += ' (Already Marked)';
      }
      
      showScreen('screen-success');
      toast('✅ Attendance marked successfully!', 'success');
    } else {
      // Failure screen
      document.getElementById('failure-msg').textContent = data.error || 'Check-in failed. Please ensure you are logged in and scan again.';
      showScreen('screen-failure');
      toast('❌ Check-in Failed', 'error');
    }

  } catch (error) {
    console.error('Auto check-in error:', error);
    document.getElementById('failure-msg').textContent = 'Network or server error. Please make sure you are connected to the class Wi-Fi and try again.';
    showScreen('screen-failure');
    toast('❌ Error connecting to server', 'error');
  }
}

function goToLoginScreen() {
  stopCamera();
  clearAlert();
  localStorage.clear();
  window.location.href = 'login.html';
}

let currentFacingMode = 'user';

// Camera control
function applyMirrorState() {
  const video = document.getElementById('student-video');
  if (video) {
    video.style.transform = isMirrored ? 'scaleX(-1)' : 'none';
  }
}

async function flipStudentCamera() {
  currentFacingMode = currentFacingMode === 'user' ? 'environment' : 'user';
  isMirrored = (currentFacingMode === 'user');
  
  toast(currentFacingMode === 'user' ? '📷 Switched to Front Camera' : '📷 Switched to Back Camera', 'success');
  
  if (stream) {
    stopCamera();
    try {
      await startCamera();
    } catch (e) {
      console.error('Error restarting camera on switch:', e);
    }
  } else {
    applyMirrorState();
  }
}

let uploadedImageData = null;

function handleStudentFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = function(e) {
    uploadedImageData = e.target.result;

    // Stop camera streaming and hide video
    stopCamera();

    const video = document.getElementById('student-video');
    const preview = document.getElementById('student-uploaded-preview');
    if (video) video.style.display = 'none';
    if (preview) {
      preview.src = uploadedImageData;
      preview.style.display = 'block';
    }

    document.getElementById('student-cam-status').textContent = '📁 Photo Uploaded: ' + file.name;
    toast('📷 Photo file loaded! Click Capture & Check-In to verify.', 'info');
  };
  reader.readAsDataURL(file);
}

async function startCamera() {
  uploadedImageData = null;
  const video = document.getElementById('student-video');
  const preview = document.getElementById('student-uploaded-preview');
  if (video) video.style.display = 'block';
  if (preview) {
    preview.src = '';
    preview.style.display = 'none';
  }

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { 
        width: { ideal: 640 }, 
        height: { ideal: 480 }, 
        facingMode: currentFacingMode 
      }
    });

    video.srcObject = stream;
    applyMirrorState();
    document.getElementById('student-cam-status').textContent = '🟢 Camera Active';
  } catch (err) {
    console.error('Camera access error:', err);
    showAlert('❌ Cannot access front camera. Please grant camera permission in your browser or check connection.', 'error');
    document.getElementById('student-cam-status').textContent = '❌ Camera Error';
    throw err;
  }
}

function stopCamera() {
  if (stream) {
    stream.getTracks().forEach(t => t.stop());
    stream = null;
  }
  const video = document.getElementById('student-video');
  if (video) {
    video.srcObject = null;
  }
}

async function goToCameraScreen() {
  const roll = document.getElementById('student-roll').value.trim().toUpperCase();
  if (!roll) {
    showAlert('⚠️ Please enter your registered Roll Number.', 'warning');
    return;
  }
  
  clearAlert();
  showScreen('screen-camera');
  
  try {
    await startCamera();
  } catch (err) {
    // Already handled in startCamera
  }
}

async function captureAndVerify() {
  const roll = document.getElementById('student-roll').value.trim().toUpperCase();
  const video = document.getElementById('student-video');
  const canvas = document.getElementById('student-canvas');
  
  let imageData = null;

  if (uploadedImageData) {
    imageData = uploadedImageData;
  } else {
    if (!stream || video.readyState < 2) {
      toast('📷 Waiting for camera feed...', 'warning');
      return;
    }
    // Draw onto canvas
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0);
    imageData = canvas.toDataURL('image/jpeg', 0.85);
  }

  const btnCapture = document.getElementById('btn-capture');
  btnCapture.disabled = true;
  btnCapture.textContent = '⚡ Verifying...';

  try {
    // Call student verify endpoint
    const response = await fetch(`${API}/attendance/student/verify`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        roll_number: roll,
        image: imageData,
        token: token,
        subject: subject
      })
    });

    const data = await response.json();
    stopCamera();

    if (response.ok && data.verified) {
      // Success screen
      document.getElementById('success-name').textContent = data.student.name;
      document.getElementById('success-roll').textContent = data.student.roll_number;
      document.getElementById('success-subject').textContent = data.subject;
      document.getElementById('success-time').textContent = data.time;
      document.getElementById('success-confidence').textContent = `${data.confidence}% Match`;
      
      if (data.already_marked) {
        document.getElementById('success-confidence').textContent += ' (Already Marked)';
      }
      
      showScreen('screen-success');
      toast('✅ Check-in successful!', 'success');
    } else {
      // Failure screen
      document.getElementById('failure-msg').textContent = data.error || 'Verification failed. Please ensure clear lighting and try again.';
      showScreen('screen-failure');
      toast('❌ Verification Failed', 'error');
    }

  } catch (error) {
    console.error('Check-in error:', error);
    stopCamera();
    document.getElementById('failure-msg').textContent = 'Network or server error. Please make sure you are connected to the class Wi-Fi and try again.';
    showScreen('screen-failure');
    toast('❌ Error connecting to server', 'error');
  } finally {
    btnCapture.disabled = false;
    btnCapture.textContent = '📸 Capture & Check-In';
  }
}

async function retryVerification() {
  clearAlert();
  showScreen('screen-camera');
  try {
    await startCamera();
  } catch (err) {
    // Already handled
  }
}
