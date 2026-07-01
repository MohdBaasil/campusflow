"""
Notification Service for College Management System.
Handles email notifications (with log fallback) and formatting for database alerts.
"""
import json
import os
import smtplib
import threading
import urllib.request
import urllib.error
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from backend.database.db import Notification

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMAIL_LOG_PATH = os.path.join(BASE_DIR, 'data', 'emails_sent.log')
SMS_LOG_PATH = os.path.join(BASE_DIR, 'data', 'sms_sent.log')
os.makedirs(os.path.dirname(EMAIL_LOG_PATH), exist_ok=True)
os.makedirs(os.path.dirname(SMS_LOG_PATH), exist_ok=True)

def load_env():
    # Load .env file if present
    env_path = os.path.join(BASE_DIR, '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    parts = line.split('=', 1)
                    key = parts[0].strip()
                    val = parts[1].strip().strip("'").strip('"')
                    os.environ[key] = val

load_env()

# SMTP Config (optional - fallback to log file if not set or fails)
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'no-reply@college.edu')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
RESEND_FROM_EMAIL = os.environ.get('RESEND_FROM_EMAIL', 'onboarding@resend.dev')

def send_email_async(to_email, subject, body_html, body_text=None):
    """Start a background thread to send an email or log it."""
    thread = threading.Thread(target=_send_email, args=(to_email, subject, body_html, body_text))
    thread.daemon = True
    thread.start()

def _send_email(to_email, subject, body_html, body_text=None):
    """Actual email sending execution (SendGrid first, then SMTP, then file log fallback)."""
    success = False

    # Determine if the single body provided is HTML or plain text
    if body_text is None:
        # Check if the body looks like HTML
        body_html_stripped = body_html.strip() if body_html else ""
        is_html = (body_html_stripped.startswith('<') or 
                   any(tag in body_html_stripped.lower() for tag in ['<html>', '<body>', '<p>', '<br>', '<div>', '</span>', '</td>']))
        
        if is_html:
            import re
            html_text = body_html
            # Create a simple plain text fallback by replacing structural tags and stripping HTML
            plain_text = (body_html
                          .replace('<br>', '\n')
                          .replace('<br/>', '\n')
                          .replace('<br />', '\n')
                          .replace('</p>', '\n\n')
                          .replace('</div>', '\n')
                          .replace('</li>', '\n'))
            plain_text = re.sub(r'<[^>]+>', '', plain_text)
            plain_text = re.sub(r'\n\s*\n', '\n\n', plain_text).strip()
        else:
            html_text = None
            plain_text = body_html
    else:
        html_text = body_html
        plain_text = body_text

    if RESEND_API_KEY and to_email:
        try:
            payload = {
                'from': RESEND_FROM_EMAIL,
                'to': [to_email],
                'subject': subject,
            }
            if html_text:
                payload['html'] = html_text
            if plain_text:
                payload['text'] = plain_text

            req = urllib.request.Request(
                'https://api.resend.com/emails',
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'Authorization': f'Bearer {RESEND_API_KEY}',
                    'Content-Type': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                },
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=20) as response:
                if response.status in (200, 201, 202):
                    success = True
                    print(f"[Email] Resend email successfully sent to {to_email}: {subject}")
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode('utf-8')
                print(f"[Email] Resend sending failed with HTTP {e.code}: {err_body}. Trying SMTP fallback.")
            except Exception:
                print(f"[Email] Resend sending failed with HTTP {e.code}. Trying SMTP fallback.")
        except Exception as e:
            print(f"[Email] Resend sending failed ({e}). Trying SMTP fallback.")

    if not success and SMTP_USER and SMTP_PASSWORD and to_email:
        try:
            if html_text:
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = SENDER_EMAIL
                msg['To'] = to_email

                part1 = MIMEText(plain_text, 'plain')
                msg.attach(part1)
                part2 = MIMEText(html_text, 'html')
                msg.attach(part2)
            else:
                msg = MIMEText(plain_text, 'plain')
                msg['Subject'] = subject
                msg['From'] = SENDER_EMAIL
                msg['To'] = to_email

            if SMTP_PORT == 465:
                with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
                    server.login(SMTP_USER, SMTP_PASSWORD)
                    server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
            else:
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(SMTP_USER, SMTP_PASSWORD)
                    server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
            success = True
            print(f"[Email] Real email successfully sent to {to_email}: {subject}")
        except Exception as e:
            print(f"[Email] Real SMTP sending failed ({e}). Falling back to log file.")

    if not success:
        # Fallback to local log file
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_entry = f"=========================================\n" \
                        f"TIMESTAMP: {timestamp}\n" \
                        f"TO: {to_email}\n" \
                        f"FROM: {SENDER_EMAIL}\n" \
                        f"SUBJECT: {subject}\n" \
                        f"-----------------------------------------\n" \
                        f"BODY:\n{plain_text}\n" \
                        f"=========================================\n\n"
            with open(EMAIL_LOG_PATH, 'a', encoding='utf-8') as f:
                f.write(log_entry)
            print(f"[Email] Logged email to {to_email}: {subject}")
        except Exception as e:
            print(f"[Email] Failed to write log: {e}")

def send_sms_async(to_phone, message):
    """Start a background thread to send an SMS or log it."""
    thread = threading.Thread(target=_send_sms, args=(to_phone, message))
    thread.daemon = True
    thread.start()

def _send_sms(to_phone, message):
    """Simulate sending SMS by logging to data/sms_sent.log."""
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"=========================================\n" \
                    f"TIMESTAMP: {timestamp}\n" \
                    f"TO (PHONE): {to_phone}\n" \
                    f"MESSAGE: {message}\n" \
                    f"=========================================\n\n"
        with open(SMS_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        print(f"[SMS] Logged SMS to {to_phone}: {message[:40]}...")
    except Exception as e:
        print(f"[SMS] Failed to write SMS log: {e}")

def notify_absence(db, student, subject_name, session_date, new_pct):
    """Notify student of absence from a class session and log in DB."""
    subject = f"Absence Alert: {subject_name} Class on {session_date}"
    body_text = f"Dear {student.name},\n\n" \
                f"You were marked ABSENT for the {subject_name} class held on {session_date}.\n" \
                f"Please note that maintaining a high attendance rate is critical to your academic standing.\n" \
                f"Your current attendance percentage has been updated to {new_pct:.1f}%.\n\n" \
                f"Best regards,\n" \
                f"College Management Admin"
                
    sent_via = []
    # 1. Send email (async)
    if student.email:
        send_email_async(student.email, subject, body_text)
        sent_via.append('email')
    if getattr(student, 'alt_email', None):
        send_email_async(student.alt_email, subject, body_text)
        if 'email' not in sent_via:
            sent_via.append('email')
        
    # 2. Send SMS/mobile alert (async)
    if student.phone:
        sms_msg = f"CMS Absence Alert: Dear {student.name}, you were marked ABSENT for the {subject_name} class on {session_date}. Attendance: {new_pct:.1f}%."
        send_sms_async(student.phone, sms_msg)
        sent_via.append('sms')
    if getattr(student, 'alt_phone', None):
        sms_msg = f"CMS Absence Alert: Dear {student.name}, you were marked ABSENT for the {subject_name} class on {session_date}. Attendance: {new_pct:.1f}%."
        send_sms_async(student.alt_phone, sms_msg)
        if 'sms' not in sent_via:
            sent_via.append('sms')
        
    # 3. Add to database notifications
    notif = Notification(
        student_id=student.id,
        type='absence',
        message=f"You were marked ABSENT in {subject_name} on {session_date}.",
        sent_via='+'.join(sent_via) if sent_via else 'email',
        status='sent'
    )
    db.add(notif)

def notify_low_attendance(db, student, new_pct):
    """Notify student when attendance falls below 75% and log in DB."""
    if new_pct < 75.0:
        subject = f"Urgent: Low Attendance Warning ({new_pct:.1f}%)"
        body_text = f"Dear {student.name},\n\n" \
                    f"Your cumulative attendance percentage has dropped to {new_pct:.1f}%, which is below the minimum required 75%.\n" \
                    f"Please contact your department coordinator as soon as possible to avoid being barred from writing final exams.\n\n" \
                    f"Best regards,\n" \
                    f"College Management Admin"
                   
        sent_via = []
        # 1. Send email (async)
        if student.email:
            send_email_async(student.email, subject, body_text)
            sent_via.append('email')
        if getattr(student, 'alt_email', None):
            send_email_async(student.alt_email, subject, body_text)
            if 'email' not in sent_via:
                sent_via.append('email')
            
        # 2. Send SMS (async)
        if student.phone:
            sms_msg = f"CMS Warning: Dear {student.name}, your attendance has dropped to {new_pct:.1f}%, which is below the minimum required 75%."
            send_sms_async(student.phone, sms_msg)
            sent_via.append('sms')
        if getattr(student, 'alt_phone', None):
            sms_msg = f"CMS Warning: Dear {student.name}, your attendance has dropped to {new_pct:.1f}%, which is below the minimum required 75%."
            send_sms_async(student.alt_phone, sms_msg)
            if 'sms' not in sent_via:
                sent_via.append('sms')
            
        # 3. Add to database notifications
        notif = Notification(
            student_id=student.id,
            type='low_attendance',
            message=f"Warning: Your attendance has dropped below 75% to {new_pct:.1f}%.",
            sent_via='+'.join(sent_via) if sent_via else 'email',
            status='sent'
        )
        db.add(notif)
        return True
    return False

def build_marks_published_notification(student_name, student_roll, subject_name, test_type, marks_obtained, max_marks):
    """Format the subject and body for marks publication emails."""
    subject = f"New Internal Marks Published: {subject_name}"
    
    plain_body = f"Dear {student_name} ({student_roll}),\n\n" \
                 f"Your internal marks for {subject_name} ({test_type}) have been published.\n" \
                 f"Marks Obtained: {marks_obtained} / {max_marks}\n\n" \
                 f"Please log in to the Student Portal to view full details.\n\n" \
                 f"Best regards,\n" \
                 f"College Management Admin"
                 
    html_body = f"""
    <html><body style="font-family: 'Segoe UI', sans-serif; padding: 20px;">
        <div style="background: linear-gradient(135deg, #667eea, #764ba2); padding: 20px; border-radius: 12px 12px 0 0; text-align: center;">
            <h2 style="color: white; margin: 0;">📋 Marks Published</h2>
        </div>
        <div style="background: white; padding: 20px; border-radius: 0 0 12px 12px; border: 1px solid #ddd; box-shadow: 0 2px 10px rgba(0,0,0,0.05);">
            <p>Dear {student_name} ({student_roll}),</p>
            <p>Your internal marks for <strong>{subject_name}</strong> (<em>{test_type}</em>) have been published.</p>
            <p style="font-size: 16px; font-weight: bold;">Marks: {marks_obtained} / {max_marks}</p>
            <p>Please log in to the Student Portal to view full details.</p>
            <p style="color: #777; font-size: 13px; margin-top: 20px;">— College Management System</p>
        </div>
    </body></html>
    """
    return subject, html_body, plain_body
