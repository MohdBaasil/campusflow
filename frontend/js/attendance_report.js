/**
 * attendance_report.js
 * Controls fetching, rendering, searching, and exporting student attendance logs.
 */

const API = window.location.protocol === 'file:' ? 'http://127.0.0.1:5000' : '';
let reportData = [];

document.addEventListener('DOMContentLoaded', () => {
  loadAttendanceReport();
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

// Fetch report data
async function loadAttendanceReport() {
  const dept = document.getElementById('filter-dept').value;
  const range = document.getElementById('filter-range').value;
  
  let url = `${API}/api/attendance/percentage/report?`;
  if (dept && dept !== 'All') {
    url += `department=${encodeURIComponent(dept)}&`;
  }
  
  if (range === 'good') {
    url += `min_pct=75&`;
  } else if (range === 'warning') {
    url += `min_pct=50&max_pct=74.99&`;
  } else if (range === 'critical') {
    url += `max_pct=49.99&`;
  }
  
  try {
    const res = await fetch(url);
    const data = await res.json();
    
    // Set summary counters
    document.getElementById('summary-total-students').textContent = data.summary.total_students || 0;
    document.getElementById('summary-average-attendance').textContent = `${data.summary.average_percentage || 0}%`;
    document.getElementById('summary-low-attendance').textContent = data.summary.below_75 || 0;
    document.getElementById('summary-critical-attendance').textContent = data.summary.below_50 || 0;
    
    reportData = data.report || [];
    renderReportTable();
    
  } catch (err) {
    console.error(err);
    toast('❌ Error loading attendance reports.', 'error');
  }
}

// Filter change handler
function onFilterChange() {
  // If department or range changed, refetch from API. If search changes, render local table filter
  const searchVal = document.getElementById('search-input').value.trim();
  if (searchVal === '') {
    loadAttendanceReport();
  } else {
    renderReportTable();
  }
}

// Render report rows with search query filter
function renderReportTable() {
  const tbody = document.getElementById('report-table-body');
  tbody.innerHTML = '';
  
  const searchVal = document.getElementById('search-input').value.toLowerCase().trim();
  
  const filtered = reportData.filter(r => {
    return !searchVal || r.name.toLowerCase().includes(searchVal) || r.roll_number.toLowerCase().includes(searchVal);
  });
  
  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align: center; color: var(--text-muted);">
          No matching student records found.
        </td>
      </tr>
    `;
    return;
  }
  
  filtered.forEach(r => {
    const pct = r.attendance_percentage;
    let badgeClass = 'badge-success';
    let statusText = 'Good';
    
    if (pct >= 75) {
      badgeClass = 'badge-success';
      statusText = 'Good (>=75%)';
    } else if (pct >= 60) {
      badgeClass = 'badge-orange';
      statusText = 'Warning';
    } else if (pct >= 50) {
      badgeClass = 'badge-danger';
      statusText = 'Low (<75%)';
    } else {
      badgeClass = 'badge-danger';
      statusText = 'Critical (<50%)';
    }
    
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${r.roll_number}</strong></td>
      <td>${r.name}</td>
      <td>${r.department}</td>
      <td>${r.total_present}</td>
      <td>${r.total_classes}</td>
      <td>
        <span style="font-weight: 800; color: ${pct < 75 ? 'var(--red)' : 'var(--green)'}">
          ${pct.toFixed(1)}%
        </span>
      </td>
      <td>
        <span class="badge ${badgeClass} ${pct < 50 ? 'status-text-critical' : ''}">
          ${statusText}
        </span>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

// Export active table data as CSV
function exportAttendanceReport() {
  const searchVal = document.getElementById('search-input').value.toLowerCase().trim();
  const filtered = reportData.filter(r => {
    return !searchVal || r.name.toLowerCase().includes(searchVal) || r.roll_number.toLowerCase().includes(searchVal);
  });
  
  if (filtered.length === 0) {
    toast('⚠️ No records to export.', 'warning');
    return;
  }
  
  let csvContent = "data:text/csv;charset=utf-8,";
  csvContent += "Roll Number,Name,Department,Attended Classes,Total Classes,Percentage,Status\n";
  
  filtered.forEach(r => {
    const status = r.attendance_percentage >= 75 ? "Good" : (r.attendance_percentage >= 50 ? "Warning" : "Critical");
    csvContent += `"${r.roll_number}","${r.name}","${r.department}",${r.total_present},${r.total_classes},${r.attendance_percentage.toFixed(1)},"${status}"\n`;
  });
  
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", `attendance_report_${new Date().toISOString().slice(0,10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  toast('📥 CSV report download triggered!', 'success');
}
