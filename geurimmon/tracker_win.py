"""Windows 입력 측정: pynput 전역 마우스 리스너 + ctypes. '왼쪽 버튼을 누른 채 이동'한 거리만 cm 로 환산.
- 이동 이벤트마다 '커서가 있는 모니터'를 찾아 그 모니터의 물리 px폭으로 mm/px 계산
- 모니터 목록·실측 mm 는 별도 스레드가 2초마다 갱신(콜백 안에서는 캐시만 읽음)
- 디버그: config.py 에 DEBUG_TRACKER = True → 모니터별 px/mm/mm_per_px 를 콘솔 + %APPDATA%\\Geurimmon\\tracker_debug.txt 에 기록"""
import ctypes, math, os, sys, threading, time
from ctypes import wintypes
from . import config

WIN = sys.platform == "win32"
DEFAULT_MM_PER_PX = 25.4 / 110
JUMP_MM = 150.0          # 한 이벤트에서 이 거리(mm) 넘게 순간이동하면 좌표 점프로 보고 무시 (px 가 아니라 mm 기준 → 4K/배율과 무관)
RESCAN_SEC = 2.0

class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]
class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32)]
class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("DeviceName", wintypes.WCHAR * 32), ("DeviceString", wintypes.WCHAR * 128),
                ("StateFlags", wintypes.DWORD), ("DeviceID", wintypes.WCHAR * 128), ("DeviceKey", wintypes.WCHAR * 128)]

if WIN:
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumDisplayMonitors.argtypes = [ctypes.c_void_p, ctypes.c_void_p, MONITORENUMPROC, ctypes.c_void_p]
    user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    user32.EnumDisplayDevicesW.argtypes = [ctypes.c_wchar_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    gdi32.CreateDCW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_void_p]; gdi32.CreateDCW.restype = ctypes.c_void_p
    gdi32.GetDeviceCaps.argtypes = [ctypes.c_void_p, ctypes.c_int]
    gdi32.DeleteDC.argtypes = [ctypes.c_void_p]

def _log(msg):
    if not getattr(config, "DEBUG_TRACKER", False): return
    print(msg)
    try:
        from .store import DIR
        with open(os.path.join(DIR, "tracker_debug.txt"), "a", encoding="utf-8") as f: f.write(msg + "\n")
    except Exception:
        pass

def _set_thread_dpi():
    """이 스레드만 Per-Monitor V2 로 지정 (-4). 프로세스 전체 설정은 건드리지 않으므로 Qt 가 이미 설정했어도 충돌 없음."""
    try:
        user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        pass

def parse_edid(e):
    """EDID 바이트 → 가로 mm (실패 0). 첫 상세 타이밍(66~68바이트)이 가장 정밀, 없으면 기본 cm(21바이트)."""
    if len(e) < 128: return 0.0
    w = e[66] | ((e[68] & 0xF0) << 4)
    if 100 <= w <= 2500: return float(w)
    cm = e[21]                                   # 16:9 같은 '화면비'만 들어있는 경우(작은 값)는 걸러냄
    return float(cm * 10) if cm >= 20 and e[22] != 0 else 0.0     # 20cm 미만(16x9 등)은 화면비 값으로 간주

def edid_mm(dev_name):
    try:
        import winreg
        i = 0
        while True:
            d = DISPLAY_DEVICEW(); d.cb = ctypes.sizeof(d)
            if not user32.EnumDisplayDevicesW(dev_name, i, ctypes.byref(d), 1): break    # 1 = EDD_GET_DEVICE_INTERFACE_NAME
            i += 1
            parts = d.DeviceID.split("#")                    # \\?\DISPLAY#GSM5B09#5&...#{guid}
            if len(parts) < 3: continue
            key = r"SYSTEM\CurrentControlSet\Enum\DISPLAY\%s\%s\Device Parameters" % (parts[1], parts[2])
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
                w = parse_edid(bytes(winreg.QueryValueEx(k, "EDID")[0]))
            if w: return w
    except Exception:
        pass
    return 0.0

def caps_mm(dev_name):                               # 2순위: GetDeviceCaps(HORZSIZE) (드라이버가 틀린 값을 주는 경우 많음)
    hdc = gdi32.CreateDCW("DISPLAY", dev_name, None, None)
    if not hdc: return 0.0
    try: return float(gdi32.GetDeviceCaps(hdc, 4))
    finally: gdi32.DeleteDC(hdc)

def scan_monitors():
    out = []
    def cb(hmon, hdc, lprc, lparam):
        mi = MONITORINFOEXW(); mi.cbSize = ctypes.sizeof(mi)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            r = mi.rcMonitor; mm = edid_mm(mi.szDevice); src = "EDID"
            if not mm: mm = caps_mm(mi.szDevice); src = "GetDeviceCaps"
            out.append(dict(name=mi.szDevice, x0=r.left, y0=r.top, x1=r.right, y1=r.bottom, w=r.right - r.left, mm=mm, src=src))
        return True
    user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(cb), None)
    return out

def pick_monitor(mons, x, y):
    for m in mons:
        if m["x0"] <= x < m["x1"] and m["y0"] <= y < m["y1"]: return m
    return min(mons, key=lambda m: max(m["x0"] - x, 0, x - m["x1"] + 1) ** 2 + max(m["y0"] - y, 0, y - m["y1"] + 1) ** 2) if mons else None

def mm_per_px(mon, w_mm):
    if not mon or mon["w"] <= 0: return DEFAULT_MM_PER_PX
    if w_mm and w_mm > 0: return w_mm / mon["w"]                    # 판 타블렛/Cintiq 작업영역 → 활성 모니터 전체에 매핑
    if 50 < mon["mm"] < 2500: return mon["mm"] / mon["w"]           # 화면 실측
    return DEFAULT_MM_PER_PX

class Tracker:
    def __init__(self, on_move, get_device):
        self.on_move, self.get_device = on_move, get_device
        self.status = "starting"; self.last = None; self.mons = []; self._dbg = 0; self._sig = None

    def start(self):
        threading.Thread(target=self._scan_loop, daemon=True).start()
        threading.Thread(target=self._listen, daemon=True).start()

    def _scan_loop(self):
        _set_thread_dpi()
        while True:
            try:
                mons = scan_monitors()
                if mons:
                    self.mons = mons                               # 통째로 교체 (콜백은 읽기만)
                    sig = [(m["name"], m["w"], m["mm"]) for m in mons]
                    if sig != self._sig:
                        self._sig = sig
                        for m in mons:
                            _log(f"[monitor] {m['name']} {m['w']}px x {m['y1'] - m['y0']}px  mm={m['mm']:.1f}({m['src']})  mm/px={mm_per_px(m, 0):.5f}")
            except Exception as ex:
                _log(f"[scan error] {ex}")
            time.sleep(RESCAN_SEC)

    def _listen(self):
        try:
            from pynput import mouse
            self._left = mouse.Button.left
            with mouse.Listener(on_move=self._on_move, on_click=self._on_click) as lis:
                self.status = "ok"; lis.join()
        except Exception as ex:
            _log(f"[listener error] {ex}")
        self.status = "error"

    def _on_click(self, x, y, button, pressed):
        try:
            if button == self._left: self.last = (x, y) if pressed else None
        except Exception:
            pass

    def _on_move(self, x, y):                                    # 가벼운 연산만. 예외가 나도 리스너가 죽지 않게 보호
        try:
            if self.last is None: return
            lx, ly = self.last; self.last = (x, y)
            d = math.hypot(x - lx, y - ly)
            if d <= 0: return
            mon = pick_monitor(self.mons, x, y)
            mpp = mm_per_px(mon, (self.get_device() or {}).get("w_mm") or 0)
            mm = d * mpp
            if mm > JUMP_MM: return                              # 순간이동 무시 (기준점은 이미 갱신됨)
            if self._dbg < 5 and getattr(config, "DEBUG_TRACKER", False):
                self._dbg += 1; pt = wintypes.POINT(); user32.GetCursorPos(ctypes.byref(pt))
                _log(f"[move] pynput=({x},{y}) GetCursorPos=({pt.x},{pt.y}) monitor={mon['name'] if mon else None} mm/px={mpp:.5f}")
            self.on_move(mm / 10.0)
        except Exception:
            pass
