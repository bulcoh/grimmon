import collections, threading, random, datetime, time, uuid
from . import config
from .sprites import BASE_COLOR, SHAPE_PIXELS, SHAPES

SIZE = 32
EMPTY = -1
PALETTE = [round(255 - i * 255 / 15) for i in range(16)]  # 0=흰색 ... 15=검정

def defaults():
    return {"total_cm": 0.0, "daily": {}, "gauge_cm": 0.0, "gift_ready": False,
            "hatched": False, "owned": [0] * 16, "grid": [EMPTY] * (SIZE * SIZE),
            "name": "", "device": None, "always_on_top": False,
            "close_to_tray": True, "tray_hint_shown": False, "setup_done": False,
            "unseen": 0, "uid": uuid.uuid4().hex, "shape_done": False}

def fmt_distance(cm, hatched):
    return f"{cm / 100:.2f}m" if hatched else f"{int(cm)}cm"

class Game:
    def __init__(self, store):
        self.store = store
        self.lock = threading.Lock()
        self.s = defaults()
        self.s.update(store.load() or {})
        self.dirty = False
        self._win, self._wsum = collections.deque(), 0.0      # 속도 상한용: 최근 1초간 인정된 거리

    # 입력 스레드에서 호출됨: 메모리 갱신만 한다 (디스크 저장 금지)
    def add_distance(self, cm):
        now = time.monotonic(); win = self._win                # 어떤 1초 구간에서도 MAX_CM_PER_SEC(기본 140cm)까지만 인정
        while win and now - win[0][0] > 1.0: self._wsum -= win.popleft()[1]
        cm = min(cm, max(0.0, getattr(config, "MAX_CM_PER_SEC", 140.0) - self._wsum))
        if cm <= 0: return
        win.append((now, cm)); self._wsum += cm
        with self.lock:
            s = self.s
            s["total_cm"] += cm
            d = datetime.date.today().isoformat()
            s["daily"][d] = s["daily"].get(d, 0.0) + cm
            if s["hatched"] and not s["gift_ready"]:
                s["gauge_cm"] += cm
                if s["gauge_cm"] >= config.GIFT_CM:
                    s["gauge_cm"] = config.GIFT_CM
                    s["gift_ready"] = True
            self.dirty = True

    def today_cm(self):
        return self.s["daily"].get(datetime.date.today().isoformat(), 0.0)

    def _grant(self, n):
        colors = [random.randrange(16) for _ in range(n)]
        with self.lock:
            for c in colors:
                self.s["owned"][c] += 1
            self.dirty = True
        return colors

    def hatch(self):
        with self.lock:
            self.s["hatched"] = True
            self.s["gauge_cm"] = 0.0
        colors = self._grant(50)                    # 랜덤 픽셀 50개
        with self.lock:
            self.s["owned"][BASE_COLOR] += SHAPE_PIXELS   # 기본 도형(옅은 흰색) 재료
            self.s["unseen"] = 0
        return colors

    def claim_gift(self):
        """게이지 보상: 랜덤 5~7개. 지급·저장은 애니메이션과 무관하게 먼저 처리."""
        if not self.s["gift_ready"]:
            return []
        with self.lock:
            self.s["gift_ready"] = False
            self.s["gauge_cm"] = 0.0
        colors = self._grant(random.randint(5, 7))
        with self.lock:
            self.s["unseen"] += len(colors)
        return colors

    def apply_shape(self, name):                 # 처음 고른 기본 도형으로 캐릭터 시작
        with self.lock:
            g, free = [EMPTY] * (SIZE * SIZE), self.s["owned"][BASE_COLOR]
            for i in SHAPES[name]:
                if free > 0: g[i] = BASE_COLOR; free -= 1
            self.s["grid"] = g; self.s["shape_done"] = True; self.dirty = True

    def reset_progress(self):                    # 디버그: 알부터 다시 (기기/프로그램 설정은 유지, uid 새로 발급)
        with self.lock:
            keep = {k: self.s[k] for k in ("device", "always_on_top", "close_to_tray", "tray_hint_shown", "setup_done")}
            self.s = defaults(); self.s.update(keep); self.dirty = True

    def placed(self):
        c = [0] * 16
        for v in self.s["grid"]:
            if v >= 0:
                c[v] += 1
        return c

    def set_character(self, grid, name):
        with self.lock:
            self.s["grid"] = list(grid)
            self.s["name"] = name.strip() or "그림몬"
            self.dirty = True

    def save(self):
        with self.lock:
            if self.dirty:
                self.store.save(self.s)
                self.dirty = False
