import os, glob, re
for file in glob.glob('frontend/*.html'):
    with open(file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # insert lecturer portal before Take Attendance
    replacement = r'<a href="lecturer_dashboard.html" class="nav-item">\n        <span class="nav-icon">👩‍🏫</span><span>Lecturer Portal</span>\n      </a>\n      <a href="attendance.html" class="nav-item">'
    
    if 'Lecturer Portal' not in text:
        text = re.sub(r'<a href="attendance\.html" class="nav-item">', replacement, text)
        
    with open(file, 'w', encoding='utf-8') as f:
        f.write(text)
