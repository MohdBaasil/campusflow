// Auth guard — redirect to login if not staff
if (localStorage.getItem("user_type") !== "staff") {
    window.location.href = "login.html";
}

/* ── Reports JavaScript ── */
const API = window.location.protocol === 'file:' ? 'http://127.0.0.1:5000/api' : '/api';

let allRecords = [];
let subjectChart = null;

// ── Toast ─────────────────────────────────────
function toast(msg, type = 'info') {
  const tc = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  t.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${msg}</span>`;
  tc.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

// ── Load Subjects into Filter ─────────────────
async function loadSubjectFilter() {
  try {
    const res = await fetch(`${API}/subjects`);
    const subjects = await res.json();
    const sel = document.getElementById('filter-subject');
    subjects.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s;
      opt.textContent = s;
      sel.appendChild(opt);
    });
  } catch (e) {}
}

// ── Load Records ──────────────────────────────
async function loadRecords() {
  const date = document.getElementById('filter-date').value;
  const subject = document.getElementById('filter-subject').value;
  const dept = document.getElementById('filter-dept').value;

  const params = new URLSearchParams();
  if (date) params.set('date', date);
  if (subject && subject !== 'All') params.set('subject', subject);
  if (dept && dept !== 'All') params.set('department', dept);

  try {
    const res = await fetch(`${API}/attendance/records?${params}`);
    allRecords = await res.json();
    renderTable(allRecords);
    updateSummary(allRecords);
    renderSubjectChart(allRecords);
  } catch (e) {
    document.getElementById('records-tbody').innerHTML =
      '<tr><td colspan="9"><div class="empty-state"><div class="empty-title">Cannot connect to server</div></div></td></tr>';
  }
}

// ── Render Table ──────────────────────────────
function renderTable(records) {
  const tbody = document.getElementById('records-tbody');
  document.getElementById('records-count').textContent = `${records.length} records`;

  if (!records.length) {
    tbody.innerHTML = '<tr><td colspan="9"><div class="empty-state"><div class="empty-icon">📋</div><div class="empty-title">No records found</div><div class="empty-sub">Adjust filters or take attendance first.</div></div></td></tr>';
    return;
  }

  tbody.innerHTML = records.map((r, i) => `
    <tr>
      <td>${i + 1}</td>
      <td><strong>${r.student_name}</strong></td>
      <td><span class="badge badge-blue">${r.roll_number}</span></td>
      <td>${r.department}</td>
      <td>${r.subject}</td>
      <td>${r.date}</td>
      <td>${r.time}</td>
      <td><span class="badge badge-success">✓ ${r.status}</span></td>
      <td>${r.confidence ? `<span style="color:var(--accent-cyan); font-weight:600;">${r.confidence}%</span>` : '–'}</td>
    </tr>
  `).join('');
}

// ── Summary Stats ─────────────────────────────
function updateSummary(records) {
  document.getElementById('rep-total').textContent = records.length;
  document.getElementById('rep-unique').textContent = new Set(records.map(r => r.student_id)).size;
  document.getElementById('rep-subjects').textContent = new Set(records.map(r => r.subject)).size;
  document.getElementById('rep-dates').textContent = new Set(records.map(r => r.date)).size;
}

// ── Subject Chart ─────────────────────────────
function renderSubjectChart(records) {
  const ctx = document.getElementById('subject-chart').getContext('2d');
  if (subjectChart) subjectChart.destroy();

  // Count by subject
  const subjectCounts = {};
  records.forEach(r => {
    subjectCounts[r.subject] = (subjectCounts[r.subject] || 0) + 1;
  });

  const labels = Object.keys(subjectCounts);
  const values = Object.values(subjectCounts);

  if (!labels.length) {
    ctx.canvas.parentElement.innerHTML = '<div class="empty-state"><div class="empty-icon">📊</div><div class="empty-title">No data to chart</div></div>';
    return;
  }

  const colors = ['#4f8ef7','#00d4ff','#00e676','#ff9800','#a855f7','#ff4757','#ffd700','#00bcd4'];

  subjectChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Attendance Records',
        data: values,
        backgroundColor: colors.slice(0, labels.length),
        borderRadius: 6,
        borderSkipped: false
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#8899b8', font: { size: 11 } } },
        y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#8899b8', font: { size: 11 }, stepSize: 1 }, beginAtZero: true }
      }
    }
  });
}

// ── Export CSV ────────────────────────────────
async function exportCSV() {
  try {
    const a = document.createElement('a');
    a.href = `${API}/attendance/export`;
    a.download = '';
    a.click();
    toast('📥 CSV export started.', 'success');
  } catch (e) {
    toast('❌ Export failed.', 'error');
  }
}

// ── Reset Filters ─────────────────────────────
function resetFilters() {
  document.getElementById('filter-date').value = '';
  document.getElementById('filter-subject').value = 'All';
  document.getElementById('filter-dept').value = 'All';
  loadRecords();
}

// ── Init ──────────────────────────────────────
loadSubjectFilter();
loadRecords();
