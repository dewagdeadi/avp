@echo off
echo [%date% %time%] Running auto-clip...
cd /d D:\royek\saas\backend
venv\Scripts\python.exe auto_clip.py
echo [%date% %time%] Auto-clip finished.
