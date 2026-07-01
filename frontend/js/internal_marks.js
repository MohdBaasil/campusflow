/**
 * internal_marks.js
 * Controls assessment marks entry, displays spreadsheet, calculates average/pass rates, and handles bulk updates.
 */

const API = window.location.protocol === 'file:' ? 'http://127.0.0.1:5000' : '';
let lecturerData = null;
let currentSubject = null;
let studentsList = [];
let existingMarksMap = new Map(); // student_id -> marks record

document.addEventListener('DOMContentLoaded', () => {
  const stored = localStorage.getItem('user_data');
  if (stored) {
    lecturerData = JSON.parse(stored);
  }
  
  loadLecturerSubjects();
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

// Fetch lecturer's subjects to populate dropdown
async function loadLecturerSubjects() {
  if (!lecturerData) return;
  try {
    const res = await fetch(`${API}/api/subjects/list?department=${lecturerData.department}`);
    const subjects = await res.json();
    
    // Filter to this lecturer's subjects
    const mySubjects = subjects.filter(s => s.lecturer_id === lecturerData.id);
    
    const select = document.getElementById('filter-subject');
    select.innerHTML = '<option value="">— Select Subject —</option>';
    
    mySubjects.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.id;
      opt.textContent = `${s.code} — ${s.name}`;
      select.appendChild(opt);
    });
    
  } catch (err) {
    console.error('Failed to load subjects:', err);
    toast('❌ Error loading subjects dropdown.', 'error');
  }
}

// Handle change in filters
function onFilterChange() {
  fetchMarksData();
}

// Update Max Marks input in the table rows
function updateMaxMarks(val) {
  document.querySelectorAll('.table-max-marks').forEach(input => {
    input.value = val;
  });
  calculateRealtimeStats();
}

// Fetch students and existing marks report
async function fetchMarksData() {
  const subjectId = document.getElementById('filter-subject').value;
  const examType = document.getElementById('filter-exam').value;
  
  if (!subjectId) {
    const tbody = document.getElementById('marks-table-body');
    tbody.innerHTML = `
      <tr>
        <td colspan="5" style="text-align: center; color: var(--text-muted);">
          Please select a subject above to load student records.
        </td>
      </tr>
    `;
    document.getElementById('marks-stats-row').style.display = 'none';
    return;
  }
  
  try {
    // 1. Get Subject details to get department
    const subRes = await fetch(`${API}/api/subjects/list?department=${lecturerData.department}`);
    const subjects = await subRes.json();
    currentSubject = subjects.find(s => s.id === parseInt(subjectId));
    
    // 2. Fetch all students matching subject department
    const stuRes = await fetch(`${API}/api/students`);
    const students = await stuRes.json();
    studentsList = students.filter(s => s.department === currentSubject.department);
    if (studentsList.length === 0) {
      studentsList = students; // Fallback
    }
    
    // 3. Fetch existing marks report
    const marksRes = await fetch(`${API}/api/marks/report?subject_id=${subjectId}&exam_type=${examType}`);
    const reportData = await marksRes.json();
    
    // Map existing marks
    existingMarksMap.clear();
    if (reportData.marks) {
      reportData.marks.forEach(m => {
        existingMarksMap.set(m.student_id, m);
      });
    }
    
    renderMarksTable();
    
  } catch (err) {
    console.error(err);
    toast('❌ Error loading marks data.', 'error');
  }
}

// Render marks spreadsheet table
function renderMarksTable() {
  const tbody = document.getElementById('marks-table-body');
  tbody.innerHTML = '';
  
  const maxMarks = document.getElementById('input-max-marks').value;
  
  if (studentsList.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" style="text-align: center; color: var(--text-muted);">
          No registered students found in this department.
        </td>
      </tr>
    `;
    document.getElementById('marks-stats-row').style.display = 'none';
    return;
  }
  
  studentsList.forEach(s => {
    const existing = existingMarksMap.get(s.id);
    const obtainedVal = existing ? existing.obtained_marks : 0;
    const maxVal = existing ? existing.max_marks : maxMarks;
    const remarksVal = existing ? (existing.remarks || '') : '';
    
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${s.roll_number}</strong></td>
      <td>${s.name}</td>
      <td>
        <input class="form-control marks-input student-obtained-input" 
               type="number" 
               data-student-id="${s.id}" 
               value="${obtainedVal}" 
               min="0" 
               max="${maxVal}" 
               step="0.5" 
               oninput="onObtainedMarksChange(this)" />
      </td>
      <td>
        <input class="form-control marks-input table-max-marks" 
               type="number" 
               value="${maxVal}" 
               disabled />
      </td>
      <td>
        <input class="form-control remarks-input student-remarks-input" 
               type="text" 
               data-student-id="${s.id}" 
               value="${remarksVal}" 
               placeholder="No remarks" />
      </td>
    `;
    tbody.appendChild(tr);
  });
  
  document.getElementById('marks-stats-row').style.display = 'flex';
  calculateRealtimeStats();
}

// Validate obtained marks on change
function onObtainedMarksChange(input) {
  const maxMarks = parseFloat(document.getElementById('input-max-marks').value);
  let val = parseFloat(input.value);
  if (isNaN(val)) val = 0;
  
  if (val < 0) {
    input.value = 0;
    toast('⚠️ Marks cannot be negative.', 'warning');
  } else if (val > maxMarks) {
    input.value = maxMarks;
    toast(`⚠️ Marks cannot exceed the maximum marks (${maxMarks}).`, 'warning');
  }
  
  calculateRealtimeStats();
}

// Calculate spreadsheet statistics in real-time
function calculateRealtimeStats() {
  const inputs = document.querySelectorAll('.student-obtained-input');
  if (inputs.length === 0) return;
  
  const maxMarks = parseFloat(document.getElementById('input-max-marks').value) || 100;
  
  let total = 0;
  let highest = -Infinity;
  let lowest = Infinity;
  let passCount = 0;
  
  inputs.forEach(input => {
    let val = parseFloat(input.value);
    if (isNaN(val)) val = 0;
    
    total += val;
    if (val > highest) highest = val;
    if (val < lowest) lowest = val;
    
    // Pass condition: >= 40%
    if (maxMarks > 0 && (val / maxMarks) >= 0.4) {
      passCount++;
    }
  });
  
  const avg = total / inputs.length;
  const passRate = (passCount / inputs.length) * 100;
  
  document.getElementById('stat-avg').textContent = avg.toFixed(1);
  document.getElementById('stat-highest').textContent = highest.toFixed(1);
  document.getElementById('stat-lowest').textContent = lowest.toFixed(1);
  document.getElementById('stat-pass-rate').textContent = `${passRate.toFixed(1)}%`;
}

// Save marks bulk POST submission
async function saveMarksBulk() {
  const subjectId = document.getElementById('filter-subject').value;
  const examType = document.getElementById('filter-exam').value;
  const maxMarks = document.getElementById('input-max-marks').value;
  
  if (!subjectId) {
    toast('⚠️ Please select a subject first.', 'warning');
    return;
  }
  
  const inputs = document.querySelectorAll('.student-obtained-input');
  const remarksInputs = document.querySelectorAll('.student-remarks-input');
  
  const marksData = [];
  inputs.forEach((input, index) => {
    const studentId = parseInt(input.getAttribute('data-student-id'));
    const obtained = parseFloat(input.value) || 0;
    const remarks = remarksInputs[index].value.trim();
    
    marksData.push({
      student_id: studentId,
      obtained_marks: obtained,
      remarks: remarks || null
    });
  });
  
  const btn = document.getElementById('btn-save-marks');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Saving & Publishing...';
  
  try {
    const res = await fetch(`${API}/api/marks/bulk`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        subject_id: parseInt(subjectId),
        exam_type: examType,
        max_marks: parseFloat(maxMarks),
        marks: marksData
      })
    });
    const data = await res.json();
    
    if (data.success) {
      toast(`✅ Marks published successfully! (${data.message})`, 'success');
      fetchMarksData(); // Reload
    } else {
      toast(`❌ Error: ${data.error}`, 'error');
    }
  } catch (err) {
    console.error(err);
    toast('❌ Network error saving marks.', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '💾 Save & Publish Marks';
  }
}
