import math, os, struct, sys, time, wave
from .store import DIR
SR = 22050

def _env(i, n, a=0.05, power=1.2):
    t = i / n; return min(1.0, t / a) * (1 - t) ** power
def sweep(f0, f1, d, vol=0.5):                    # 음이 오르거나 내리는 뚜웅~
    n = int(SR * d); ph = 0.0; out = []
    for i in range(n):
        ph += 2 * math.pi * (f0 + (f1 - f0) * i / n) / SR
        out.append((math.sin(ph) + 0.25 * math.sin(2 * ph)) * _env(i, n) * vol)
    return out
def tone(f, d, vol=0.3, dec=4.0):                 # 반짝이는 음
    n = int(SR * d)
    return [math.sin(2 * math.pi * f * i / SR) * min(1, i / (SR * 0.004)) * math.exp(-dec * i / n) * vol for i in range(n)]
def mix(*parts):
    out = [0.0] * max(o + len(s) for o, s in parts)
    for o, s in parts:
        for i, v in enumerate(s): out[o + i] += v
    return out
def _wav(path, x):
    pk = max(1.0, max(abs(v) for v in x))
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(v / pk * 18000)) for v in x))

SOUNDS = {
    "tap_up":   lambda: sweep(320, 560, 0.28, 0.55),
    "tap_down": lambda: sweep(560, 300, 0.28, 0.55),
    "pop":      lambda: mix((0, sweep(500, 140, 0.09, 0.6)), *[(int(SR * (0.05 + 0.06 * k)), tone(f, 0.25)) for k, f in enumerate([1568, 1976, 2349, 2794, 3136])]),
    "ready":    lambda: mix((0, tone(1319, 0.18, 0.35, 3.0)), (int(SR * 0.13), tone(1760, 0.3, 0.35, 3.0))),   # 게이지 가득 참 띠링~
    "beep":     lambda: tone(988, 0.06, 0.4, 5.0),
}

class Sfx:
    """Use preloaded native sound objects for short UI effects."""
    def __init__(self):
        self.paths, self.snd, self._t = {}, {}, 0.0
        try:
            d = os.path.join(DIR, "sfx"); os.makedirs(d, exist_ok=True)
            for name, make in SOUNDS.items():
                path = os.path.join(d, f"{name}_v2.wav")
                if not os.path.exists(path): _wav(path, make())
                self.paths[name] = path
            if sys.platform == "darwin":
                from AppKit import NSSound
                for n, pth in self.paths.items():
                    sd = NSSound.alloc().initWithContentsOfFile_byReference_(pth, True)
                    if sd: sd.setVolume_(0.8); self.snd[n] = sd
            elif sys.platform == "win32":
                # Keep each effect loaded and reusable. PlaySound starts a new
                # Windows multimedia playback request on every call, which can
                # add noticeable latency for short UI sounds.
                from PySide6.QtCore import QUrl
                from PySide6.QtMultimedia import QSoundEffect
                for n, pth in self.paths.items():
                    sd = QSoundEffect()
                    sd.setSource(QUrl.fromLocalFile(pth))
                    sd.setVolume(0.8)
                    self.snd[n] = sd
        except Exception as ex:
            print("sound disabled:", ex); self.paths = {}
    def play(self, name):
        if name not in self.paths: return
        if name == "beep":                       # 연속 드래그 시 과도한 중첩 방지
            now = time.time()
            if now - self._t < 0.03: return
            self._t = now
        try:
            if sys.platform == "darwin":
                sd = self.snd.get(name)
                if sd: sd.stop(); sd.play()
            elif sys.platform == "win32":
                sd = self.snd.get(name)
                if sd and sd.isLoaded():
                    sd.stop(); sd.play()
        except Exception: pass
