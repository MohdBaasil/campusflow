// Auth guard — redirect to login if not staff
if (localStorage.getItem("user_type") !== "staff") {
    window.location.href = "login.html";
}

/* ── Dashboard JavaScript ── */
const API = window.location.protocol === 'file:' ? 'http://127.0.0.1:5000/api' : '/api';
let trendChart, deptChart;

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

// ── Count-up animation ────────────────────────
function animateCount(el, target, suffix = '') {
  if (!el) return;
  const start = parseInt(el.textContent) || 0;
  const duration = 800;
  const step = (timestamp) => {
    if (!step.startTime) step.startTime = timestamp;
    const progress = Math.min((timestamp - step.startTime) / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(start + (target - start) * ease) + suffix;
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// ── Date display ──────────────────────────────
function updateDate() {
  const el = document.getElementById('topbar-date');
  if (el) el.textContent = new Date().toLocaleDateString('en-IN', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
  });
}

// ── Update model status card ──────────────────
function updateModelCard(trained, numClasses) {
  const icon = document.getElementById('model-icon');
  const statusText = document.getElementById('model-status-text');
  const classesText = document.getElementById('model-classes-text');
  const banner = document.getElementById('model-banner');

  if (trained) {
    if (icon) icon.textContent = '✅';
    if (statusText) statusText.textContent = 'Model Trained';
    if (classesText) classesText.textContent = `${numClasses} identit${numClasses === 1 ? 'y' : 'ies'} learned`;
    if (banner) banner.style.display = 'none';
  } else {
    if (icon) icon.textContent = '⚠️';
    if (statusText) { statusText.textContent = 'Not Trained'; statusText.style.color = 'var(--orange)'; }
    if (classesText) classesText.textContent = 'Register students then train';
    if (banner) banner.style.display = 'flex';
  }
}

// ── Load Dashboard ────────────────────────────
async function loadDashboard() {
  try {
    const res = await fetch(`${API}/dashboard`);
    if (!res.ok) throw new Error('Server not reachable');
    const data = await res.json();

    animateCount(document.getElementById('stat-students'), data.total_students);
    animateCount(document.getElementById('stat-present'), data.present_today);
    animateCount(document.getElementById('stat-classes'), data.num_classes);

    const rateEl = document.getElementById('stat-rate');
    if (rateEl) rateEl.textContent = `${data.attendance_rate}% attendance rate`;

    // Hero numbers
    animateCount(document.getElementById('hero-students'), data.total_students);
    animateCount(document.getElementById('hero-present'), data.present_today);
    const heroRate = document.getElementById('hero-rate');
    if (heroRate) heroRate.textContent = data.attendance_rate + '%';

    updateModelCard(data.model_trained, data.num_classes);
    renderTrendChart(data.trend);
    renderDeptChart(data.departments);
  } catch (err) {
    const alertArea = document.getElementById('alert-area');
    if (alertArea) alertArea.innerHTML = `
      <div class="alert alert-error">
        ❌ Cannot connect to server. Make sure <strong>run.py</strong> is running at port 5000.
      </div>`;
    const statusEl = document.getElementById('server-status');
    if (statusEl) statusEl.textContent = 'Server Offline';
  }
}

// ── Recent Records ────────────────────────────
async function loadRecentRecords() {
  try {
    const res = await fetch(`${API}/attendance/records`);
    const records = await res.json();
    const tbody = document.getElementById('recent-tbody');
    if (!tbody) return;
    if (!records.length) {
      tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state">
        <div class="empty-icon">📋</div>
        <div class="empty-title">No records yet</div>
        <div class="empty-sub">Take attendance to see records here.</div>
      </div></td></tr>`;
      return;
    }
    tbody.innerHTML = records.slice(0, 10).map(r => `
      <tr>
        <td><strong>${r.student_name}</strong></td>
        <td><span class="badge badge-blue">${r.roll_number}</span></td>
        <td>${r.department}</td>
        <td>${r.subject}</td>
        <td>${r.date}</td>
        <td>${r.time}</td>
        <td><span class="badge badge-success">✓ ${r.status}</span></td>
        <td style="color:var(--cyan); font-weight:700;">${r.confidence ? r.confidence + '%' : '–'}</td>
      </tr>`).join('');
  } catch (e) { console.error('Records error:', e); }
}

// ── Charts ────────────────────────────────────
function renderTrendChart(trend) {
  const canvas = document.getElementById('trend-chart');
  if (!canvas) return;
  if (trendChart) trendChart.destroy();

  const labels = trend.map(t => {
    const d = new Date(t.date);
    return d.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' });
  });

  trendChart = new Chart(canvas.getContext('2d'), {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Students Present',
        data: trend.map(t => t.count),
        borderColor: '#a855f7',
        backgroundColor: 'rgba(168,85,247,0.08)',
        fill: true, tension: 0.45,
        pointBackgroundColor: '#a855f7',
        pointBorderColor: '#0a0118',
        pointBorderWidth: 2,
        pointRadius: 5,
        pointHoverRadius: 8
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#9490b8', font: { size: 11 } } },
        y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#9490b8', font: { size: 11 }, stepSize: 1 }, beginAtZero: true }
      }
    }
  });
}

function renderDeptChart(departments) {
  const wrapper = document.getElementById('dept-chart-wrapper');
  const canvas = document.getElementById('dept-chart');
  if (!canvas) return;
  if (deptChart) deptChart.destroy();

  const labels = Object.keys(departments);
  const values = Object.values(departments);

  if (!labels.length) {
    if (wrapper) wrapper.innerHTML = `<div class="empty-state">
      <div class="empty-icon">🏫</div>
      <div class="empty-title">No students registered</div>
    </div>`;
    return;
  }

  const colors = ['#a855f7','#4f8ef7','#10b981','#f59e0b','#ec4899','#06b6d4','#ef4444','#8b5cf6'];

  deptChart = new Chart(canvas.getContext('2d'), {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors.slice(0, labels.length),
        borderColor: '#07060f',
        borderWidth: 3,
        hoverOffset: 8
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right', labels: { color: '#9490b8', font: { size: 11 }, padding: 14, boxWidth: 12 } }
      }
    }
  });
}

// ── Train Model ───────────────────────────────
async function trainModel() {
  const btns = [document.getElementById('train-btn'), document.getElementById('train-btn-2')];
  btns.forEach(b => { if (b) { b.disabled = true; b.innerHTML = '<span class="spinner"></span> Training...'; } });

  const alertArea = document.getElementById('alert-area');
  if (alertArea) alertArea.innerHTML = `<div class="alert alert-info">⏳ Training ArcFace+SVM model… this may take a few seconds.</div>`;

  try {
    const res = await fetch(`${API}/train`, { method: 'POST' });
    const data = await res.json();

    if (alertArea) alertArea.innerHTML = '';

    if (data.success) {
      toast(`🧠 ${data.message}`, 'success');
      if (alertArea) alertArea.innerHTML = `<div class="alert alert-success">✅ ${data.message}</div>`;
      setTimeout(() => { if (alertArea) alertArea.innerHTML = ''; }, 5000);
      loadDashboard();
    } else {
      toast(`❌ ${data.message}`, 'error');
      if (alertArea) alertArea.innerHTML = `<div class="alert alert-error">❌ ${data.message}</div>`;
    }
  } catch (e) {
    toast('❌ Cannot connect to server.', 'error');
    if (alertArea) alertArea.innerHTML = `<div class="alert alert-error">❌ Cannot reach server.</div>`;
  } finally {
    btns.forEach(b => {
      if (b) { b.disabled = false; b.innerHTML = b.id === 'train-btn' ? '🧠 Train Model' : '🧠 Train Model'; }
    });
  }
}

// ── Init ──────────────────────────────────────
updateDate();
loadDashboard();
loadRecentRecords();
setInterval(() => { loadDashboard(); loadRecentRecords(); }, 30000);
