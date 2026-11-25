import math, os, random, struct, time, wave
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
def swish(d, vol=0.3, lo=0.05, hi=0.6):           # 샥~ (필터가 열리는 노이즈)
    n = int(SR * d); y = 0.0; out = []
    for i in range(n):
        y += (lo + (hi - lo) * i / n) * (random.uniform(-1, 1) - y)
        out.append(y * math.sin(math.pi * i / n) * vol * 3)
    return out
def mix(*parts):
    out = [0.0] * max(o + len(s) for o, s in parts)
    for o, s in parts:
        for i, v in enumerate(s): out[o + i] += v
    return out
def _wav(path, x):
    pk = max(1.0, max(abs(v) for v in x))
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(v / pk * 28000)) for v in x))

SOUNDS = {
    "tap_up":   lambda: sweep(320, 560, 0.28, 0.55),
    "tap_down": lambda: sweep(560, 300, 0.28, 0.55),
    "pop":      lambda: mix((0, sweep(500, 140, 0.09, 0.6)), *[(int(SR * (0.05 + 0.06 * k)), tone(f, 0.25)) for k, f in enumerate([1568, 1976, 2349, 2794, 3136])]),
    "absorb":   lambda: mix((0, swish(0.12, 0.3, 0.1, 0.7)), (int(SR * 0.09), swish(0.12, 0.3, 0.1, 0.7)), (int(SR * 0.18), swish(0.14, 0.3, 0.1, 0.7))),
    "whoosh":   lambda: swish(0.2, 0.3, 0.05, 0.5),
    "ready":    lambda: mix((0, tone(1319, 0.18, 0.35, 3.0)), (int(SR * 0.13), tone(1760, 0.3, 0.35, 3.0))),   # 게이지 가득 참 띠링~
    "beep":     lambda: tone(988, 0.06, 0.4, 5.0),
}

class Sfx:
    def __init__(self):
        self.fx, self._t = {}, 0.0
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QSoundEffect
            d = os.path.join(DIR, "sfx"); os.makedirs(d, exist_ok=True)
            for name, make in SOUNDS.items():
                path = os.path.join(d, f"{name}_v1.wav")
                if not os.path.exists(path): _wav(path, make())
                e = QSoundEffect(); e.setSource(QUrl.fromLocalFile(path)); e.setVolume(0.6); self.fx[name] = e
        except Exception as ex:
            print("sound disabled:", ex)
    def play(self, name):
        e = self.fx.get(name)
        if not e: return
        if name == "beep":                       # 연속 드래그 시 과도한 중첩 방지
            now = time.time()
            if now - self._t < 0.03: return
            self._t = now
        try: e.play()
        except Exception: pass
