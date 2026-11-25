@echo off
REM 윈도우용 딸깍 빌드 (윈도우 PC에서 실행). Python 3.12 설치 필요: python.org
cd /d %~dp0
py -3.12 -m venv .venv || (echo Python 3.12 를 설치하세요 & pause & exit /b 1)
call .venv\Scripts\activate
pip install -q -r requirements.txt pyinstaller
rmdir /s /q build dist 2>nul
pyinstaller --noconfirm --clean --windowed --name Grimmon --add-data "assets;assets" main.py
powershell -Command "Compress-Archive -Path dist\Grimmon -DestinationPath Grimmon-win.zip -Force"
echo 완료: Grimmon-win.zip
pause
