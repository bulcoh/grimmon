APP_NAME = "Grimmon"
VERSION = "0.1.0"          # 새 릴리즈를 낼 때 이 숫자를 올리고, 깃헙 태그도 v0.1.1 처럼 맞추세요

# ★★★ 깃헙 주소는 여기에 넣으세요 ★★★
# https://github.com/<GITHUB_OWNER>/<GITHUB_REPO>
GITHUB_OWNER = "bulcoh"
GITHUB_REPO = "grimmon"

HATCH_CM = 100.0           # 알이 깨지는 거리 (1m)
GIFT_CM = 1000.0          #게이지 양
JUMP_PT = 150              # 한 이벤트에서 이 포인트 이상 움직이면 좌표 점프로 보고 무시
SAVE_INTERVAL_MS = 10000
UPDATE_CHECK_HOURS = 6
DEBUG = False

# 명예의 전당 서버 (Cloudflare Workers 주소)
SERVER_URL = "https://grimmon-board.grimmon.workers.dev"   # 예: "https://grimmon-board.내서브도메인.workers.dev"
SERVER_KEY = "check"
