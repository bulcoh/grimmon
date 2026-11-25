#!/bin/bash
# 최초 1회 실행: ./setup.sh
cd "$(dirname "$0")"
PY=$(command -v python3.13 || command -v python3.12 || command -v python3)
echo "사용할 파이썬: $PY ($($PY --version))"
$PY -m venv .venv && source .venv/bin/activate && pip install -U pip && pip install -r requirements.txt
