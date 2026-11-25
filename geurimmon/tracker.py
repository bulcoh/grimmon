import math, threading, time
from . import config
try:
    import Quartz
except Exception:  # pyobjc 미설치
    Quartz = None

DEFAULT_MM_PER_PT = 25.4 / 110

class Tracker:
    """macOS 전역 이벤트 탭(listen-only)으로 '왼쪽 버튼 드래그'만 측정.
    펜 접촉 드래그도 OS에서는 왼쪽 드래그로 들어오며, 호버(mouseMoved)는 구독하지 않는다.
    한 종류의 이벤트만 구독하므로 펜/마우스 중복 계산이 없다."""

    def __init__(self, on_move, get_device):
        self.on_move, self.get_device = on_move, get_device
        self.status = "starting"   # starting / ok / permission / error
        self.last = None
        self._displays, self._disp_t = [], 0.0

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        if Quartz is None:
            self.status = "error"; return
        try:
            Quartz.CGRequestListenEventAccess()
        except Exception:
            pass
        while True:  # 권한 허용 후 재시도
            mask = (Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseDown)
                    | Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseUp)
                    | Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseDragged))
            self.tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap, Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionListenOnly, mask, self._cb, None)
            if self.tap:
                break
            self.status = "permission"
            time.sleep(3)
        src = Quartz.CFMachPortCreateRunLoopSource(None, self.tap, 0)
        Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetCurrent(), src, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(self.tap, True)
        self.status = "ok"
        Quartz.CFRunLoopRun()

    def _refresh_displays(self):
        now = time.time()
        if now - self._disp_t < 2:
            return
        self._disp_t = now
        try:
            _, ids, _ = Quartz.CGGetActiveDisplayList(16, None, None)
            out = []
            for d in ids:
                b, sz = Quartz.CGDisplayBounds(d), Quartz.CGDisplayScreenSize(d)
                out.append((b.origin.x, b.origin.y, b.size.width, b.size.height, sz.width))
            self._displays = out
        except Exception:
            self._displays = []

    def _mm_per_pt(self, x, y):
        self._refresh_displays()
        disp = next((d for d in self._displays
                     if d[0] <= x < d[0] + d[2] and d[1] <= y < d[1] + d[3]), None)
        dev = self.get_device() or {}
        if disp and disp[2] > 0:
            if dev.get("w_mm"):                 # 판 타블렛: 작업영역 → 화면 전체 매핑 가정
                return dev["w_mm"] / disp[2]
            if disp[4] > 0:                     # 화면 실측 폭(mm)
                return disp[4] / disp[2]
        return DEFAULT_MM_PER_PT

    def _cb(self, proxy, etype, event, refcon):
        if etype in (0xFFFFFFFE, 0xFFFFFFFF):   # 탭이 비활성화됨 → 재활성화
            Quartz.CGEventTapEnable(self.tap, True)
            return event
        try:
            loc = Quartz.CGEventGetLocation(event)
            if etype == Quartz.kCGEventLeftMouseDown:
                self.last = (loc.x, loc.y)
            elif etype == Quartz.kCGEventLeftMouseUp:
                self.last = None
            elif etype == Quartz.kCGEventLeftMouseDragged:
                if self.last is not None:
                    d = math.hypot(loc.x - self.last[0], loc.y - self.last[1])
                    if 0 < d < config.JUMP_PT:   # 비정상 점프는 제외하고 기준점만 갱신
                        self.on_move(d * self._mm_per_pt(loc.x, loc.y) / 10.0)
                self.last = (loc.x, loc.y)
        except Exception:
            pass   # 입력 감지 오류가 앱/드로잉을 방해하지 않도록
        return event
