# 그림몬 (맥 베타 0.1.0)
1. `./setup.sh`   (최초 1회. 가상환경 + 패키지 설치)
2. `./run.sh`
3. 시스템 설정 → 개인정보 보호 및 보안 → **입력 모니터링**에 터미널(또는 VS Code)을 허용 후 재실행
## 깃헙 업데이트 알림
- `geurimmon/config.py` 의 GITHUB_OWNER / GITHUB_REPO 에 본인 깃헙 정보 입력 (저장소는 public)
- 새 버전: config.py VERSION 올리기 → 깃헙에서 Release 생성(태그 예: v0.1.1) → 실행 중인 앱이 최대 6시간 내(또는 실행 시 5초 후) 알림
- config.py, cloudflare/wrjangler.toml, cloudflare/cloudflare.key 의 key와 database_id 수정후 빌드
