@echo off
pip install -r requirements.txt
pyinstaller build.spec
echo تم بناء الملف التنفيذي في مجلد dist
pause
