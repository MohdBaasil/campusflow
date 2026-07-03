import os, glob, re
html_files = glob.glob('frontend/*.html')
for file in html_files:
    with open(file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Try literal replacement
    text = re.sub(r'<a href=.lecturer_dashboard\.html. class=.nav-item[^>]*>\s*<span class=.nav-icon.>👩‍🏫</span><span>Lecturer Portal</span>\s*</a>', '', text)
    text = re.sub(r'<a href=.class_session\.html. class=.nav-item[^>]*>\s*<span class=.nav-icon.>🎥</span><span>Live Sessions</span>\s*</a>', '<a href="attendance.html" class="nav-item">\n          <span class="nav-icon">📷</span><span>Take Attendance</span>\n        </a>', text)
    
    with open(file, 'w', encoding='utf-8') as f:
        f.write(text)
