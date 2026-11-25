#!/bin/bash
# 맥용 딸깍 빌드: 더블클릭 또는 ./build_mac.command
cd "$(dirname "$0")"
source .venv/bin/activate || { echo "먼저 ./setup.sh 를 실행하세요"; exit 1; }
pip install -q pyinstaller
rm -rf build dist *.spec
pyinstaller --noconfirm --clean --windowed --name Grimmon --add-data "assets:assets" --hidden-import Quartz main.py || exit 1
VER=$(python -c "from geurimmon import config; print(config.VERSION)")
ditto -c -k --keepParent dist/Grimmon.app "Grimmon-mac-$VER.zip"
echo "완료 → Grimmon-mac-$VER.zip"
