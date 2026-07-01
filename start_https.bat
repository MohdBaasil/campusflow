@echo off
echo ============================================================
echo   Smart Attendance System using Face Recognition (HOG)
echo   [Running in secure HTTPS mode]
echo ============================================================
echo.
echo Starting Flask server...
echo.
start "" "https://127.0.0.1:5000/static/index.html"
C:\Users\Asus\AppData\Local\Programs\Python\Python312\python.exe run.py --https
pause
