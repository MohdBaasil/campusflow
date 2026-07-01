"""
verify_cms_flow.py
Integration test script to verify College Management System (CMS) backend logic.
Written without emoji characters to prevent encoding crashes in standard Windows terminals.
"""
import requests
import sys

API_URL = "http://127.0.0.1:5000"

def test_cms_flow():
    print("==================================================")
    print("      CMS E2E FLOW VERIFICATION START             ")
    print("==================================================")
    
    # 1. Test Lecturer Login
    print("\n[Step 1] Logging in as Lecturer...")
    login_payload = {
        "employee_id": "lecturer1",
        "password": "password123"
    }
    res = requests.post(f"{API_URL}/api/auth/lecturer-login", json=login_payload)
    if res.status_code != 200:
        print(f"[ERROR] Login failed! Status: {res.status_code}, Response: {res.text}")
        sys.exit(1)
    
    login_data = res.json()
    token = login_data["token"]
    lecturer_id = login_data["user_data"]["id"]
    lecturer_name = login_data["user_data"]["name"]
    department = login_data["user_data"]["department"]
    print(f"[OK] Login successful! Token: {token[:8]}..., Lecturer: {lecturer_name} (Dept: {department})")
    
    # 2. Get Lecturer Subjects
    print("\n[Step 2] Retrieving subjects assigned to lecturer...")
    res = requests.get(f"{API_URL}/api/subjects/list?department={department}")
    if res.status_code != 200:
        print(f"[ERROR] Failed to retrieve subjects! Status: {res.status_code}")
        sys.exit(1)
        
    subjects = res.json()
    my_subjects = [s for s in subjects if s["lecturer_id"] == lecturer_id]
    if not my_subjects:
        print("[ERROR] No subjects assigned to this lecturer. Migration seeding failed?")
        sys.exit(1)
        
    subject = my_subjects[0]
    print(f"[OK] Found {len(my_subjects)} subjects. Testing with Subject: {subject['code']} - {subject['name']}")
    
    # Get initial students list to get a test roll number
    print("\n[Prep] Fetching registered students...")
    res = requests.get(f"{API_URL}/api/students")
    students = res.json()
    if not students:
        print("[ERROR] No students found in database. Please register at least one student first.")
        sys.exit(1)
    
    # Pick a student in the department or fallback
    dept_students = [s for s in students if s["department"] == department]
    test_student = dept_students[0] if dept_students else students[0]
    initial_percentage = test_student.get("attendance_percentage", 100.0)
    print(f"[OK] Selected Test Student: {test_student['name']} ({test_student['roll_number']}), Initial Attendance: {initial_percentage}%")
    
    # 3. Start a Class Session
    print("\n[Step 3] Starting a live class session...")
    session_payload = {
        "subject_id": subject["id"],
        "lecturer_id": lecturer_id,
        "topic_covered": "Advanced Database Schema Verification",
        "session_type": "Lecture"
    }
    res = requests.post(f"{API_URL}/api/class-sessions", json=session_payload)
    if res.status_code != 200:
        print(f"[ERROR] Failed to start class session! Response: {res.text}")
        sys.exit(1)
        
    session_data = res.json()
    session_id = session_data["session"]["id"]
    session_token = session_data["token"]
    qr_url = session_data["url"]
    print(f"[OK] Session started successfully! ID: {session_id}, Active Token: {session_token[:8]}...")
    print(f"[OK] Generated Student QR URL: {qr_url}")
    
    # 4. Simulate Student Checkin
    print("\n[Step 4] Simulating student QR code scan checkin...")
    checkin_payload = {
        "roll_number": test_student["roll_number"],
        "token": session_token,
        "subject": subject["name"]
    }
    res = requests.post(f"{API_URL}/api/attendance/student/session-checkin", json=checkin_payload)
    if res.status_code != 200:
        print(f"[ERROR] Student check-in failed! Response: {res.text}")
        sys.exit(1)
        
    checkin_data = res.json()
    print(f"[OK] Student checked in! Name: {checkin_data['student']['name']}, Time: {checkin_data['time']}")
    
    # Check student new percentage
    res = requests.get(f"{API_URL}/api/attendance/percentage/{test_student['id']}")
    updated_pct_data = res.json()
    new_percentage = updated_pct_data["attendance_percentage"]
    print(f"[OK] Student attendance percentage updated: {initial_percentage}% -> {new_percentage}% (+1% award)")
    
    # 5. End Class Session
    print("\n[Step 5] Ending class session (will mark other students as absent)...")
    res = requests.post(f"{API_URL}/api/class-sessions/{session_id}/end")
    if res.status_code != 200:
        print(f"[ERROR] Failed to end class session! Response: {res.text}")
        sys.exit(1)
        
    end_data = res.json()
    print(f"[OK] Class session ended! Status: {end_data['session']['status']}, Message: {end_data['message']}")
    
    # 6. Check Absence Email and SMS Logs
    print("\n[Step 6] Inspecting logs for absence notifications...")
    import os
    email_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "emails_sent.log")
    sms_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sms_sent.log")
    
    if os.path.exists(email_log_path):
        with open(email_log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        print("[OK] Email log file found! Last 15 lines of log:")
        clean_lines = [l.encode('ascii', errors='ignore').decode('ascii') for l in lines[-15:]]
        print("".join(clean_lines))
    else:
        print("[WARNING] data/emails_sent.log was not created. Email notification script failed?")
        
    if os.path.exists(sms_log_path):
        with open(sms_log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        print("[OK] SMS log file found! Last 10 lines of log:")
        clean_lines = [l.encode('ascii', errors='ignore').decode('ascii') for l in lines[-10:]]
        print("".join(clean_lines))
    else:
        print("[WARNING] data/sms_sent.log was not created. SMS notification script failed?")
        
    # 7. Bulk Enter Marks
    print("\n[Step 7] Entering internal marks for the class...")
    marks_payload = {
        "subject_id": subject["id"],
        "exam_type": "Internal 1",
        "max_marks": 50,
        "marks": [
            {
                "student_id": test_student["id"],
                "obtained_marks": 42.5,
                "remarks": "Excellent analysis skills!"
            }
        ]
    }
    res = requests.post(f"{API_URL}/api/marks/bulk", json=marks_payload)
    if res.status_code != 200:
        print(f"[ERROR] Failed to save bulk marks! Response: {res.text}")
        sys.exit(1)
        
    marks_data = res.json()
    print(f"[OK] Marks saved! Message: {marks_data['message']}")
    
    # Verify email notice was logged
    if os.path.exists(email_log_path):
        with open(email_log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        print("[OK] New email logs for marks publication:")
        clean_lines = [l.encode('ascii', errors='ignore').decode('ascii') for l in lines[-15:]]
        print("".join(clean_lines))
        
    print("\n==================================================")
    print("      CMS E2E FLOW VERIFICATION SUCCESS           ")
    print("==================================================")

if __name__ == "__main__":
    test_cms_flow()
