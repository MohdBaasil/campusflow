// Auth guard — redirect to login if not staff
if (localStorage.getItem("user_type") !== "staff") {
    window.location.href = "login.html";
}

/* ── Register JavaScript ── */
const API = window.location.protocol === 'file:' ? 'http://127.0.0.1:5000/api' : '/api';

let stream = null;
let capturedImages = [];
const MAX_PHOTOS = 5;

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
  document.getElementById('reg-alert').innerHTML =
    `<div class="alert alert-${type}">${msg}</div>`;
}

function clearAlert() {
  document.getElementById('reg-alert').innerHTML = '';
}

// ── Step Indicator ────────────────────────────
function setStep(n) {
  for (let i = 1; i <= 4; i++) {
    const s = document.getElementById(`step-${i}`);
    if (!s) continue;
    s.classList.remove('active', 'done');
    if (i < n) s.classList.add('done');
    else if (i === n) s.classList.add('active');
  }
}

// ── Camera ────────────────────────────────────
let isMirrored = localStorage.getItem('cam_mirrored') !== 'false'; // Default to true (mirrored is standard selfie)

function applyMirrorState() {
  const video = document.getElementById('reg-video');
  if (video) {
    video.style.transform = isMirrored ? 'scaleX(-1)' : 'none';
  }
}

function flipCamera() {
  isMirrored = !isMirrored;
  localStorage.setItem('cam_mirrored', isMirrored);
  applyMirrorState();
  toast(isMirrored ? '📷 Camera view mirrored' : '📷 Camera view normal');
}

async function toggleCamera() {
  if (stream) stopCamera();
  else await startCamera();
}

async function startCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' }
    });
    const video = document.getElementById('reg-video');
    video.srcObject = stream;
    video.style.display = 'block';
    applyMirrorState();
    document.getElementById('camera-placeholder').style.display = 'none';
    document.getElementById('cam-overlay').style.display = 'block';
    document.getElementById('cam-status').style.display = 'block';
    document.getElementById('cam-toggle-btn').textContent = '⏹ Stop Camera';
    document.getElementById('cam-status').textContent = '🟢 Camera Active';
  } catch (err) {
    showAlert('❌ Camera access denied. Please allow camera permissions in your browser.', 'error');
  }
}

function stopCamera() {
  if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
  const video = document.getElementById('reg-video');
  video.srcObject = null;
  video.style.display = 'none';
  document.getElementById('camera-placeholder').style.display = 'flex';
  document.getElementById('cam-overlay').style.display = 'none';
  document.getElementById('cam-status').style.display = 'none';
  document.getElementById('cam-toggle-btn').textContent = '▶ Start Camera';
}

// ── Capture Photo ─────────────────────────────
function capturePhoto() {
  if (!stream) { showAlert('⚠️ Please start the camera first.', 'warning'); return; }
  if (capturedImages.length >= MAX_PHOTOS) {
    showAlert('✅ 5 photos captured. You can register now.', 'info'); return;
  }

  const video = document.getElementById('reg-video');
  const canvas = document.getElementById('reg-canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);
  const dataUrl = canvas.toDataURL('image/jpeg', 0.9);

  capturedImages.push(dataUrl);
  updatePhotoGrid();
  clearAlert();

  // Flash effect
  const camCont = document.querySelector('.camera-container');
  if (camCont) {
    camCont.style.filter = 'brightness(2.5)';
    setTimeout(() => camCont.style.filter = '', 120);
  }

  // Update steps
  if (capturedImages.length >= 1) setStep(2);
  if (capturedImages.length >= 3) setStep(3);
}

function updatePhotoGrid() {
  for (let i = 0; i < MAX_PHOTOS; i++) {
    const slot = document.getElementById(`slot-${i}`);
    if (!slot) continue;
    if (i < capturedImages.length) {
      slot.innerHTML = `<img src="${capturedImages[i]}" alt="Photo ${i+1}" /><div class="check">✓</div>`;
      slot.classList.add('filled');
    } else {
      slot.innerHTML = '📷';
      slot.classList.remove('filled');
    }
  }
  const pct = (capturedImages.length / MAX_PHOTOS) * 100;
  document.getElementById('photo-progress').style.width = `${pct}%`;
  document.getElementById('photo-count-label').textContent = `${capturedImages.length} / ${MAX_PHOTOS}`;
  document.getElementById('register-btn').disabled = capturedImages.length < 3;
}

function resetPhotos() {
  capturedImages = [];
  updatePhotoGrid();
  clearAlert();
  setStep(1);
}

// ── Register Student ──────────────────────────
async function registerStudent() {
  clearAlert();
  const name = document.getElementById('reg-name').value.trim();
  const roll = document.getElementById('reg-roll').value.trim();
  const dept = document.getElementById('reg-dept').value;

  if (!name) { showAlert('❌ Please enter the student\'s full name.', 'error'); return; }
  if (!roll) { showAlert('❌ Please enter the roll number.', 'error'); return; }
  if (!dept) { showAlert('❌ Please select a department.', 'error'); return; }
  if (capturedImages.length < 3) { showAlert('❌ Please capture at least 3 face photos.', 'error'); return; }

  const btn = document.getElementById('register-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Registering...';

  try {
    const res = await fetch(`${API}/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, roll_number: roll, department: dept, images: capturedImages })
    });
    const data = await res.json();

    if (res.ok) {
      showAlert(`✅ ${data.message}`, 'success');
      toast('Student registered successfully!', 'success');

      // Reset form
      document.getElementById('reg-name').value = '';
      document.getElementById('reg-roll').value = '';
      document.getElementById('reg-dept').value = '';
      resetPhotos();
      loadStudents();

      // Show train prompt
      const prompt = document.getElementById('train-prompt');
      if (prompt) prompt.style.display = 'block';
      setStep(4);
    } else {
      showAlert(`❌ ${data.error}`, 'error');
    }
  } catch (e) {
    showAlert('❌ Cannot connect to server. Is run.py running?', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '✅ Register Student';
    document.getElementById('register-btn').disabled = capturedImages.length < 3;
  }
}

// ── Train from Register Page ──────────────────
async function trainModelFromRegister() {
  const btn = document.querySelector('#train-prompt .btn-primary');
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Training...'; }

  try {
    const res = await fetch(`${API}/train`, { method: 'POST' });
    const data = await res.json();

    if (data.success) {
      toast('🧠 Model trained! Ready to take attendance.', 'success');
      document.getElementById('train-prompt').innerHTML = `
        <div class="alert alert-success">🧠 ${data.message}</div>
        <a href="attendance.html" class="btn btn-success" style="width:100%; margin-top:8px;">
          📷 Start Taking Attendance →
        </a>`;
    } else {
      toast(`❌ ${data.message}`, 'error');
      if (btn) { btn.disabled = false; btn.innerHTML = '🧠 Train Model Now'; }
    }
  } catch (e) {
    toast('❌ Server error during training.', 'error');
    if (btn) { btn.disabled = false; btn.innerHTML = '🧠 Train Model Now'; }
  }
}

// ── Load Students ─────────────────────────────
async function loadStudents() {
  const container = document.getElementById('students-list');
  try {
    const res = await fetch(`${API}/students`);
    const students = await res.json();

    if (!students.length) {
      container.innerHTML = '<div class="empty-state"><div class="empty-icon">👥</div><div class="empty-title">No students yet</div></div>';
      return;
    }

    container.innerHTML = students.map(s => `
      <div style="display:flex; align-items:center; gap:12px; padding:11px 4px; border-bottom:1px solid var(--border);">
        <div style="
          width:38px; height:38px; border-radius:50%;
          background:linear-gradient(135deg, #7c3aed, #4f46e5);
          display:flex; align-items:center; justify-content:center;
          font-weight:800; font-size:14px; color:#fff; flex-shrink:0;
          box-shadow:0 0 12px rgba(124,58,237,0.3);">
          ${s.name.charAt(0).toUpperCase()}
        </div>
        <div style="flex:1; min-width:0;">
          <div style="font-size:13px; font-weight:700; color:var(--text-primary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${s.name}</div>
          <div style="font-size:11px; color:var(--text-muted);">${s.roll_number} · ${s.department}</div>
        </div>
        <div style="display:flex; gap:6px;">
          <button class="btn btn-outline btn-sm" onclick="showQRModal(${s.id}, '${s.name.replace(/'/g,'\\\'')}', '${s.roll_number}')" title="Show QR Code" style="padding:4px 8px; font-size:11px; font-weight:600; display:flex; align-items:center; gap:4px;">📱 QR</button>
          <button class="btn btn-danger btn-sm btn-icon" onclick="deleteStudent(${s.id}, '${s.name.replace(/'/g,'\\\'')}')" title="Delete student">🗑</button>
        </div>
      </div>`).join('');
  } catch (e) {
    container.innerHTML = '<div class="empty-state"><div class="empty-title">Server not reachable</div></div>';
  }
}

async function deleteStudent(id, name) {
  if (!confirm(`Delete "${name}"? This will remove all their attendance records too.`)) return;
  try {
    const res = await fetch(`${API}/students/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if (res.ok) { toast(`🗑 ${name} deleted.`, 'info'); loadStudents(); }
    else toast(`❌ ${data.error}`, 'error');
  } catch (e) { toast('❌ Server error.', 'error'); }
}

// ── Tab Management ────────────────────────────
function switchRegTab(tab) {
  const tabSingle = document.getElementById('tab-single');
  const tabBulk = document.getElementById('tab-bulk');
  const singleFields = document.getElementById('single-form-fields');
  const bulkFields = document.getElementById('bulk-form-fields');
  const captureCard = document.getElementById('photo-capture-card');

  if (tab === 'single') {
    tabSingle.classList.add('active');
    tabSingle.style.borderBottom = '2px solid var(--purple)';
    tabSingle.style.color = 'var(--text-primary)';
    tabBulk.classList.remove('active');
    tabBulk.style.borderBottom = '2px solid transparent';
    tabBulk.style.color = 'var(--text-muted)';
    
    singleFields.style.display = 'block';
    bulkFields.style.display = 'none';
    captureCard.style.display = 'block';
  } else {
    tabBulk.classList.add('active');
    tabBulk.style.borderBottom = '2px solid var(--purple)';
    tabBulk.style.color = 'var(--text-primary)';
    tabSingle.classList.remove('active');
    tabSingle.style.borderBottom = '2px solid transparent';
    tabSingle.style.color = 'var(--text-muted)';

    singleFields.style.display = 'none';
    bulkFields.style.display = 'block';
    captureCard.style.display = 'none';
    stopCamera(); // Make sure camera is off when not registering single
  }
  clearAlert();
}

// ── Bulk Import ───────────────────────────────
async function importBulkStudents() {
  clearAlert();
  const csvFile = document.getElementById('bulk-csv').files[0];
  const zipFile = document.getElementById('bulk-zip').files[0];

  if (!csvFile) {
    showAlert('❌ Please select a Google Form responses CSV file.', 'error');
    return;
  }

  const btn = document.getElementById('bulk-import-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Importing...';

  const formData = new FormData();
  formData.append('csv', csvFile);
  if (zipFile) {
    formData.append('zip', zipFile);
  }

  try {
    const res = await fetch(`${API}/register/bulk`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();

    if (res.ok) {
      showAlert(`✅ ${data.message}`, 'success');
      toast('Bulk import completed!', 'success');
      
      // Reset inputs
      document.getElementById('bulk-csv').value = '';
      document.getElementById('bulk-zip').value = '';
      loadStudents();

      // Show alert with details if photos were imported
      const detailStr = data.details.map(d => `${d.name} (${d.roll_number}) - ${d.photos_imported} photos`).join('\n');
      console.log('Import Details:\n' + detailStr);
    } else {
      showAlert(`❌ ${data.error}`, 'error');
    }
  } catch (e) {
    showAlert('❌ Server error during bulk import.', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '🚀 Import Students';
  }
}

// ── QR Modal Management ───────────────────────
function showQRModal(studentId, name, roll) {
  document.getElementById('qr-student-name').textContent = name;
  document.getElementById('qr-student-roll').textContent = `Roll Number: ${roll}`;
  
  const qrImg = document.getElementById('qr-modal-image');
  const qrUrl = `${API}/students/${studentId}/qrcode`;
  qrImg.src = qrUrl;

  const dlLink = document.getElementById('qr-download-link');
  dlLink.href = qrUrl;
  dlLink.download = `${roll}_qr.png`;

  const modal = document.getElementById('qr-modal');
  modal.style.display = 'flex';
}

function closeQRModal() {
  const modal = document.getElementById('qr-modal');
  modal.style.display = 'none';
}

// ── Init ──────────────────────────────────────
loadStudents();
setStep(1);

// ── Photo Upload Handler ──────────────────────
function handlePhotoUpload(event) {
  const files = event.target.files;
  if (!files || files.length === 0) return;

  let loaded = 0;
  const countToLoad = Math.min(files.length, MAX_PHOTOS - capturedImages.length);
  
  if (countToLoad <= 0) {
    showAlert(`⚠️ Maximum of ${MAX_PHOTOS} photos reached. Reset or retake if needed.`, 'warning');
    return;
  }

  for (let i = 0; i < countToLoad; i++) {
    const file = files[i];
    if (!file.type.startsWith('image/')) {
      toast('❌ Only image files are allowed', 'error');
      continue;
    }

    const reader = new FileReader();
    reader.onload = function(e) {
      capturedImages.push(e.target.result);
      loaded++;
      if (loaded === countToLoad) {
        updatePhotoGrid();
        clearAlert();
        toast(`📁 Successfully loaded ${loaded} photo(s)`, 'success');
        
        // Update steps
        if (capturedImages.length >= 1) setStep(2);
        if (capturedImages.length >= 3) setStep(3);
      }
    };
    reader.readAsDataURL(file);
  }
  
  // Clear input value so same files can be re-uploaded if reset
  event.target.value = '';
}

