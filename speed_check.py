"""속도 상한 측정기 - 화면 어디서든 왼쪽 버튼(또는 펜)을 누른 채 최대한 빠르게 그어보세요.
게임과 똑같은 측정 코드·기기 설정(save.json)을 사용하므로, 여기 나오는 cm/s 가 곧 게임이 세는 속도입니다.
저장 데이터는 건드리지 않습니다.   실행: 프로젝트 폴더에서  python speed_check.py  (또는 tools/ 안에 두고 실행)"""
import collections, os, sys, threading, time
here = os.path.dirname(os.path.abspath(__file__))
for d in (here, os.path.dirname(here)):
    if os.path.isdir(os.path.join(d, "geurimmon")): sys.path.insert(0, d); break
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox
from geurimmon.store import Store
from geurimmon import tracker as T          # 맥: Quartz / 윈도우: tracker_win 으로 자동 교체

class Win(QWidget):
    WIN = (0.1, 0.25, 1.0)                  # 평균을 내는 시간 창(초)
    def __init__(self):
        super().__init__(); self.setWindowTitle("속도 상한 측정"); self.setWindowFlag(Qt.WindowStaysOnTopHint, True); self.resize(400, 560)
        self.lock = threading.Lock(); self.ev = collections.deque(); self.reset()
        dev = {"maker": "manual", "model": "24inch", "w_mm": 531, "h_mm": 299}
        self.dev_text = f"{dev['maker']} / {dev['model']}" if dev else "(기기 미설정 → 화면 실측)"
        self.tracker = T.Tracker(self.on_move, lambda: dev); self.tracker.start()
        lay = QVBoxLayout(self)
        self.pad = QLabel("여기서 (또는 화면 어디서든)\n왼쪽 버튼 / 펜을 누른 채\n최대한 빠르게 그어보세요"); self.pad.setAlignment(Qt.AlignCenter)
        self.pad.setMinimumHeight(150); self.pad.setStyleSheet("border:2px dashed #888; font-size:16px;"); lay.addWidget(self.pad)
        self.out = QLabel(); self.out.setStyleSheet("font-family:Menlo,Consolas,monospace; font-size:14px;"); lay.addWidget(self.out)
        row = QHBoxLayout(); row.addWidget(QLabel("상한 시뮬레이션 (cm/s):")); self.spin = QSpinBox(); self.spin.setRange(10, 5000); self.spin.setValue(150); row.addWidget(self.spin); lay.addLayout(row)
        b = QPushButton("초기화 (최고값 지우기)"); b.clicked.connect(self.reset); lay.addWidget(b)
        self.tm = QTimer(self); self.tm.timeout.connect(self.tick); self.tm.start(20)
    def reset(self):
        with self.lock:
            self.ev.clear(); self.max = {w: 0.0 for w in self.WIN}; self.step_max = 0.0; self.raw = 0.0; self.capped = 0.0
            self.bucket = 0.0; self.bstart = time.perf_counter()
    def on_move(self, cm):                  # 측정 스레드: 시각 기록만
        now = time.perf_counter()
        with self.lock:
            self.ev.append((now, cm)); self.bucket += cm; self.step_max = max(self.step_max, cm)
    def tick(self):
        now = time.perf_counter(); cap = self.spin.value()
        with self.lock:
            while self.ev and now - self.ev[0][0] > 1.0: self.ev.popleft()
            snap = list(self.ev)
            if now - self.bstart >= 0.1:    # 0.1초마다 '상한을 적용했다면 인정됐을 거리'를 누적
                self.raw += self.bucket; self.capped += min(self.bucket, cap * 0.1); self.bucket = 0.0; self.bstart = now
            cur = {w: sum(c for t, c in snap if now - t <= w) / w for w in self.WIN}
            for w in self.WIN: self.max[w] = max(self.max[w], cur[w])
            pct = 100 * self.capped / self.raw if self.raw > 0 else 100
            lines = [f"상태: {self.tracker.status}   기기: {self.dev_text}", "", "평균 구간      지금     최고   (cm/s)"]
            lines += [f"  {w:>4}초   {cur[w]:8.1f} {self.max[w]:8.1f}" for w in self.WIN]
            lines += ["", f"이벤트 1건 최대 이동: {self.step_max * 10:.2f} mm", f"최근 1초 이벤트 수: {len(snap)}", "",
                      f"누적 {self.raw:.1f} cm  →  상한 {cap} cm/s 적용 시 {self.capped:.1f} cm ({pct:.0f}%)"]
        self.out.setText("\n".join(lines))

if __name__ == "__main__":
    app = QApplication(sys.argv); w = Win(); w.show(); sys.exit(app.exec())
