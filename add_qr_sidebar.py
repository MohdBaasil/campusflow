import os, glob, re
html_files = glob.glob('frontend/*.html')
for file in html_files:
    with open(file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Check if QR Attendance is already added to avoid duplicates
    if 'QR Attendance' not in text:
        # We find the Take Attendance block and add QR Attendance right after it
        replacement = r'<a href="attendance.html" class="nav-item">\n          <span class="nav-icon">📷</span><span>Take Attendance</span>\n        </a>\n        <a href="qrcodes.html" class="nav-item">\n          <span class="nav-icon">📱</span><span>QR Attendance</span>\n        </a>'
        text = re.sub(r'<a href="attendance\.html" class="nav-item">\s*<span class="nav-icon">📷</span><span>Take Attendance</span>\s*</a>', replacement, text)
        
    with open(file, 'w', encoding='utf-8') as f:
        f.write(text)
