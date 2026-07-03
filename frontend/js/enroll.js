// Auth guard — redirect to login if not staff or lecturer
const _ut = localStorage.getItem('user_type');
if (_ut !== 'staff' && _ut !== 'lecturer') {
    window.location.href = 'login.html';
}

function logout() {
  localStorage.clear();
  window.location.href = 'login.html';
}

/* ── Enroll Face JavaScript ── */
const API = window.location.protocol === 'file:' ? 'http://127.0.0.1:5000/api' : '/api';

const MAX_PHOTOS = 5;
let enrollStream = null;
let isMirrored = true;
let capturedImages = [];
let selectedStudent = null;

// ── Toast ──────────────────────────────────────
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
  document.getElementById('enroll-alert').innerHTML =
    `<div class="alert alert-${type}">${msg}</div>`;
}

function clearAlert() {
  document.getElementById('enroll-alert').innerHTML = '';
}

// ── Load & display students ────────────────────
let allStudents = [];

async function loadStudents() {
  try {
    const res = await fetch(`${API}/students`);
    allStudents = await res.json();

    // Populate dropdown
    const sel = document.getElementById('enroll-student-select');
    sel.innerHTML = '<option value="">— Select Student —</option>';
    allStudents.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.id;
      opt.textContent = `${s.name}  (${s.roll_number})`;
      sel.appendChild(opt);
    });

    // Render table
    renderStudentsTable(allStudents);
    document.getElementById('students-count').textContent = `${allStudents.length} students`;
  } catch (e) {
    showAlert('❌ Cannot connect to server. Make sure run.py is running.', 'error');
  }
}

function renderStudentsTable(students) {
  const wrap = document.getElementById('students-table-wrap');
  if (!students.length) {
    wrap.innerHTML = `<div class="empty-state"><div class="empty-icon">👥</div><div class="empty-title">No students registered yet</div></div>`;
    return;
  }

  wrap.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Roll No.</th>
          <th>Department</th>
          <th style="text-align:center;">Faces</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        ${students.map(s => `
          <tr>
            <td style="font-weight:700; color:var(--text-primary);">${s.name}</td>
            <td>${s.roll_number}</td>
            <td>${s.department}</td>
            <td style="text-align:center;">
              <span class="badge ${s.face_count > 0 ? 'badge-success' : 'badge-danger'}">
                ${s.face_count > 0 ? `✓ ${s.face_count}` : '✗ None'}
              </span>
            </td>
            <td>
              <button class="btn btn-outline btn-sm" onclick="selectStudentById(${s.id})" style="padding:4px 10px; font-size:11px;">
                🤳 Enroll
              </button>
            </td>
          </tr>`).join('')}
      </tbody>
    </table>`;
}

function onStudentSelect(id) {
  if (!id) {
    selectedStudent = null;
    document.getElementById('selected-student-info').style.display = 'none';
    document.getElementById('enroll-capture-btn').disabled = true;
    document.getElementById('enroll-submit-btn').disabled = true;
    return;
  }
  selectStudentById(parseInt(id));
}

function selectStudentById(id) {
  selectedStudent = allStudents.find(s => s.id === id);
  if (!selectedStudent) return;

  // Sync dropdown
  document.getElementById('enroll-student-select').value = id;

  // Show info card
  const initials = selectedStudent.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
  document.getElementById('si-avatar').textContent = initials;
  document.getElementById('si-name').textContent = selectedStudent.name;
  document.getElementById('si-meta').textContent = `${selectedStudent.roll_number} · ${selectedStudent.department}`;

  const faceCount = selectedStudent.face_count || 0;
  const embEl = document.getElementById('si-emb');
  if (faceCount > 0) {
    embEl.innerHTML = `<span class="badge badge-success">✓ ${faceCount} face embedding(s) already saved</span>`;
  } else {
    embEl.innerHTML = `<span class="badge badge-danger">✗ No face photos yet — please enroll below</span>`;
  }

  document.getElementById('selected-student-info').style.display = 'block';
  document.getElementById('enroll-capture-btn').disabled = !enrollStream;
  updateEnrollSubmitBtn();

  // Scroll to top
  window.scrollTo({ top: 0, behavior: 'smooth' });
  clearAlert();
  toast(`Selected: ${selectedStudent.name}`, 'info');
}

// ── Camera ────────────────────────────────────
function applyMirrorState() {
  const video = document.getElementById('enroll-video');
  if (video) video.style.transform = isMirrored ? 'scaleX(-1)' : 'none';
}

function flipEnrollCamera() {
  isMirrored = !isMirrored;
  applyMirrorState();
  toast(isMirrored ? 'Camera mirrored' : 'Camera normal');
}

async function toggleEnrollCamera() {
  if (enrollStream) {
    stopEnrollCamera();
  } else {
    await startEnrollCamera();
  }
}

async function startEnrollCamera() {
  try {
    enrollStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' }
    });
    const video = document.getElementById('enroll-video');
    video.srcObject = enrollStream;
    video.style.display = 'block';
    applyMirrorState();
    document.getElementById('enroll-cam-placeholder').style.display = 'none';
    document.getElementById('enroll-cam-overlay').style.display = 'block';
    document.getElementById('enroll-cam-status').style.display = 'block';
    document.getElementById('enroll-cam-toggle').textContent = '⏹ Stop Camera';
    document.getElementById('enroll-cam-status').textContent = '🟢 Camera Active';

    if (selectedStudent) {
      document.getElementById('enroll-capture-btn').disabled = false;
    }
  } catch (err) {
    showAlert('❌ Camera access denied. Please allow camera permissions.', 'error');
  }
}

function stopEnrollCamera() {
  if (enrollStream) { enrollStream.getTracks().forEach(t => t.stop()); enrollStream = null; }
  const video = document.getElementById('enroll-video');
  video.srcObject = null;
  video.style.display = 'none';
  document.getElementById('enroll-cam-placeholder').style.display = 'flex';
  document.getElementById('enroll-cam-overlay').style.display = 'none';
  document.getElementById('enroll-cam-status').style.display = 'none';
  document.getElementById('enroll-cam-toggle').textContent = '▶ Start Camera';
  document.getElementById('enroll-capture-btn').disabled = true;
}

// ── Photo Capture & Upload ────────────────────
function captureEnrollPhoto() {
  if (!enrollStream) { toast('Start the camera first', 'warning'); return; }
  if (!selectedStudent) { toast('Select a student first', 'warning'); return; }
  if (capturedImages.length >= MAX_PHOTOS) { toast('Maximum 5 photos reached', 'info'); return; }

  const video = document.getElementById('enroll-video');
  const canvas = document.getElementById('enroll-canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);
  const dataUrl = canvas.toDataURL('image/jpeg', 0.9);

  capturedImages.push(dataUrl);
  updatePhotoGrid();
  clearAlert();

  // Flash effect
  const cont = document.getElementById('enroll-camera-container');
  cont.style.filter = 'brightness(2.5)';
  setTimeout(() => cont.style.filter = '', 120);
}

function handleEnrollFileUpload(event) {
  if (!selectedStudent) { toast('Select a student first', 'warning'); return; }
  const files = Array.from(event.target.files);
  let loaded = 0;
  files.forEach(file => {
    if (capturedImages.length >= MAX_PHOTOS) return;
    const reader = new FileReader();
    reader.onload = e => {
      capturedImages.push(e.target.result);
      loaded++;
      if (loaded === files.length || capturedImages.length >= MAX_PHOTOS) updatePhotoGrid();
    };
    reader.readAsDataURL(file);
  });
  event.target.value = '';
}

function updatePhotoGrid() {
  for (let i = 0; i < MAX_PHOTOS; i++) {
    const slot = document.getElementById(`eslot-${i}`);
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
  document.getElementById('enroll-progress').style.width = `${pct}%`;
  document.getElementById('enroll-photo-label').textContent = `${capturedImages.length} photo${capturedImages.length !== 1 ? 's' : ''}`;
  updateEnrollSubmitBtn();
}

function updateEnrollSubmitBtn() {
  const btn = document.getElementById('enroll-submit-btn');
  btn.disabled = !selectedStudent || capturedImages.length === 0;
}

function resetEnrollPhotos() {
  capturedImages = [];
  updatePhotoGrid();
  clearAlert();
}

// ── Submit Enrollment ─────────────────────────
async function submitEnrollment() {
  if (!selectedStudent) { showAlert('Please select a student.', 'warning'); return; }
  if (capturedImages.length === 0) { showAlert('Please capture or upload at least one face photo.', 'warning'); return; }

  clearAlert();
  const btn = document.getElementById('enroll-submit-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Enrolling...';

  try {
    const res = await fetch(`${API}/students/enroll-face`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        roll_number: selectedStudent.roll_number,
        images: capturedImages
      })
    });
    const data = await res.json();

    if (res.ok) {
      showAlert(`
        <strong>✅ ${data.message}</strong>
        ${data.warnings && data.warnings.length
          ? `<br/><small style="opacity:0.7;">⚠️ Warnings: ${data.warnings.join(', ')}</small>`
          : ''}
        <br/><br/>
        🧠 <strong>Next step:</strong> Go to the 
        <a href="index.html" style="color:var(--purple); text-decoration:underline;">Dashboard</a> 
        and click <strong>Train Model</strong> so face recognition works for this student.
      `, 'success');
      toast(`Face enrolled for ${selectedStudent.name}!`, 'success');
      resetEnrollPhotos();

      // Reload to reflect new face counts
      await loadStudents();

      // Re-select same student to refresh badge
      if (selectedStudent) selectStudentById(selectedStudent.id);
    } else {
      showAlert(`❌ ${data.error}`, 'error');
      toast(data.error, 'error');
    }
  } catch (e) {
    showAlert('❌ Cannot connect to server. Make sure run.py is running.', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '✅ Save Face Photos';
    updateEnrollSubmitBtn();
  }
}

// ── Init ──────────────────────────────────────
loadStudents();

