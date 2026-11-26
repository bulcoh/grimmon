import datetime, math, os, sys, random, threading, time, webbrowser
from PySide6.QtCore import (Qt, QTimer, QRectF, QPointF, Signal, QObject, QPropertyAnimation,
                            QParallelAnimationGroup, QEasingCurve, QVariantAnimation, QPoint, QRect)
from PySide6.QtGui import QPainter, QColor, QPen, QImage, QPixmap, QIcon, QFontDatabase, QFont, QShortcut, QKeySequence
from PySide6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
                               QMessageBox, QComboBox, QCheckBox, QLineEdit, QSystemTrayIcon, QScrollArea,
                               QGraphicsOpacityEffect, QInputDialog)
from . import config, board
from .game import PALETTE, SIZE, EMPTY, fmt_distance
from .devices import DEVICE_DB, SCREEN, OTHER
from .lore import LORE
from .sfx import Sfx
from .sprites import EGG_IDLE, SPRITE_GRAYS, SHAPES, BASE_COLOR, sprite_image

W, H = 220, 320
MOD = "Cmd" if sys.platform == "darwin" else "Ctrl"
GH = 244        # 거리를 누르면 홈이 내려가는 높이 (그래프 영역)
STYLE = """
QWidget#page, QDialog { background:#1E1E1E; }
QWidget { color:#e6e6e6; }
QLabel { background:transparent; }
QPushButton { background:#2a2a2a; border:1px solid #555; padding:3px 8px; }
QPushButton:hover { background:#383838; }
QPushButton#mi { text-align:center; padding:6px 14px; border:none; background:transparent; }
QPushButton#mi:hover { background:#2c2c2c; }
QPushButton#back { border:none; background:transparent; font-size:22px; padding:0; }
QComboBox, QLineEdit { background:#2a2a2a; border:1px solid #555; padding:2px 4px; }
QComboBox QAbstractItemView { background:#2a2a2a; selection-background-color:#555; }
QCheckBox::indicator { width:14px; height:14px; border:1px solid #888; background:#1E1E1E; }
QCheckBox::indicator:checked { background:#e6e6e6; }
QScrollArea { border:none; background:transparent; }
QScrollBar:vertical { width:6px; background:#1E1E1E; } QScrollBar::handle:vertical { background:#555; }
"""

def load_theme(app):
    app.setStyle("Fusion"); app.setStyleSheet(STYLE)
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # 패키징된 앱에서도 동작
    path = os.path.join(base, "assets", "DungGeunMo.ttf")
    fid = QFontDatabase.addApplicationFont(path)
    fam = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
    if not fam: print("폰트 파일을 찾지 못했어요:", path)
    f = QFont(fam[0] if fam else app.font().family()); f.setPixelSize(16); f.setStyleStrategy(QFont.NoAntialias)
    app.setFont(f); app.setWindowIcon(egg_icon())

def gray(i): v = PALETTE[i]; return QColor(v, v, v)
def fg_for(i): return "#000" if PALETTE[i] >= 128 else "#fff"
def clamp(x): return max(0.0, min(1.0, x))
def ease_out(x): return 1 - (1 - x) ** 3
def ease_in(x): return x ** 3
def page(w): w.setObjectName("page"); w.setAttribute(Qt.WA_StyledBackground, True)

def friendly(m):
    m = str(m)
    if "CERTIFICATE" in m: return "인증서 오류 (SSL)"
    if "403" in m: return "키가 달라요 (SERVER_KEY)"
    if "500" in m: return "서버 오류 (D1 테이블 확인)"
    if "nodename" in m or "resolve" in m.lower(): return "서버 주소를 찾을 수 없어요"
    return m[:40]

def grid_image(grid):
    img = QImage(SIZE, SIZE, QImage.Format_ARGB32); img.fill(0)
    for i, v in enumerate(grid):
        if v >= 0: img.setPixelColor(i % SIZE, i // SIZE, gray(v))
    return img

def asset(name):
    return os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", name)

def egg_icon():                                 # assets/icon.png 가 있으면 그것, 없으면 알 스프라이트
    p = asset("icon.png")
    return QIcon(p) if os.path.exists(p) else QIcon(QPixmap.fromImage(sprite_image(EGG_IDLE)).scaled(64, 64))

class Bus(QObject):
    moved = Signal(float)
    def __init__(self): super().__init__(); self.test_on = False; self.app_active = False

# ---------------- 캐릭터 / 알 표시 ----------------
class CharView(QWidget):
    clicked = Signal()
    def __init__(self, game, parent):
        super().__init__(parent); self.game = game; self._g = None; self._img = None; self._egg = sprite_image(EGG_IDLE)
    def mousePressEvent(self, e): self.clicked.emit()
    def paintEvent(self, _):
        p = QPainter(self); s = self.game.s; w, h = self.width(), self.height(); t = time.time()
        sc = max(1, int(min(w, h - 12) // SIZE))
        if not s["hatched"]:
            prog = min(1.0, s["total_cm"] / config.HATCH_CM)
            jig = round(math.sin(t * 9) * prog * 1.3)          # 부화가 가까울수록 더 흔들
            p.drawImage(QRectF((w - 32 * sc) // 2 + jig * sc, (h - 32 * sc) // 2, 32 * sc, 32 * sc), self._egg); return
        if all(v < 0 for v in s["grid"]):
            p.setPen(QColor("#888")); p.drawText(self.rect(), Qt.AlignCenter, "그림몬을\n성형해주세요"); return
        if s["grid"] is not self._g: self._g, self._img = s["grid"], grid_image(s["grid"])
        bx, by = int(math.sin(t * 2) * 2), int(-abs(math.sin(t * 3)) * 4)   # 통통 + 좌우 흔들
        p.setPen(Qt.NoPen); p.setBrush(QColor(0, 0, 0, 70)); p.drawEllipse(QPointF(w / 2, h - 6), SIZE * sc * 0.3, 3)
        p.drawImage(QRectF((w - 32 * sc) // 2 + bx, h - 32 * sc - 8 + by, 32 * sc, 32 * sc), self._img)

# ---------------- 픽셀 게이지 ----------------
class PixelGauge(QWidget):
    clicked = Signal()
    AW, AH, PX, B = 32, 1, 5, 2.5            # 32칸 × 두께 AH칸, 1칸=5px, 테두리 2.5px(두께의 절반). 두껍게: AH=2,3
    def __init__(self, game, parent):
        super().__init__(parent); self.game = game; self._c = {}; self.hover = False; self.hs = 0.0
    def enterEvent(self, e): self.hover = True
    def leaveEvent(self, e): self.hover = False
    def bar_center(self): return QPoint(self.width() // 2, 10)
    @staticmethod
    def _inside(px, py, x0, y0, x1, y1, r):                 # 둥근 사각형(알약) 내부 판정
        cx = min(max(px, x0 + r), x1 - r); cy = min(max(py, y0 + r), y1 - r)
        return (px - cx) ** 2 + (py - cy) ** 2 <= r * r
    def _img(self, filled, ready):
        k = (filled, ready)
        if k not in self._c:
            B = self.B; Wt = int(self.AW * self.PX + 2 * B); Ht = int(self.AH * self.PX + 2 * B)
            img = QImage(Wt, Ht, QImage.Format_ARGB32); img.fill(0)
            edge, track, fill = QColor("#8a8a8a"), QColor("#4a4a4a"), QColor("#ffffff" if ready else "#e6e6e6")
            fx = B + filled * self.PX
            for y in range(Ht):
                for x in range(Wt):
                    px, py = x + 0.5, y + 0.5
                    if not self._inside(px, py, 0, 0, Wt, Ht, 0): continue
                    inner = self._inside(px, py, B, B, Wt - B, Ht - B, 0)
                    img.setPixelColor(x, y, (fill if px < fx else track) if inner else edge)
            self._c[k] = img
        return self._c[k]
    def paintEvent(self, _):
        p = QPainter(self); s = self.game.s; ready = s["gift_ready"]
        filled = self.AW if ready else min(self.AW, int(s["gauge_cm"] / config.GIFT_CM * self.AW))
        img = self._img(filled, ready); self.hs += ((1.0 if self.hover else 0.0) - self.hs) * 0.35
        p.save(); p.translate(self.width() / 2, 10)
        k = 1 + 0.12 * self.hs                                              # 호버 시 살짝 커짐
        if ready: k *= 1 + 0.06 * (0.5 + 0.5 * math.sin(time.time() * 5))   # 가득 차면 은은하게
        p.scale(k, k); p.drawImage(QPointF(-img.width() / 2, -img.height() / 2), img); p.restore()
        if self.hs > 0.05:                                                  # 호버 시 수치
            cur = config.GIFT_CM if ready else s["gauge_cm"]; f = p.font(); f.setPixelSize(14); p.setFont(f)
            p.setPen(QColor(200, 200, 200, int(255 * self.hs)))
            p.drawText(QRectF(0, 20, self.width(), 18), Qt.AlignCenter, f"{cur / 100:.2f}m/{config.GIFT_CM / 100:.2f}m")
    def mousePressEvent(self, e):
        if self.game.s["gift_ready"]: self.clicked.emit()

# ---------------- 보상 오버레이 (게이지 → 3배 픽셀 → 그림몬) ----------------
class ClaimOverlay(QWidget):
    done = Signal(); absorbing = Signal()
    TOK, GAP = 26, 30
    def __init__(self, parent):
        super().__init__(parent); self.hide(); self.colors = []
        self.timer = QTimer(self); self.timer.timeout.connect(self.tick)
    def start(self, colors, src, dst):          # 게이지 위 한 줄로 좌르륵
        self.setGeometry(0, 0, W, H); self.colors = colors; self.src = QPointF(src); self.dst = QPointF(dst)
        n = len(colors); y = self.src.y() - 30
        self.tg = [QPointF(W / 2 + (j - (n - 1) / 2) * self.GAP, y) for j in range(n)]
        self.t, self.phase = 0.0, 0; self.raise_(); self.show(); self.timer.start(16)
    def tick(self):
        self.t += 0.016; n = len(self.colors)
        if self.phase == 0 and self.t >= 0.05 * n + 0.3: self.phase, self.t = 1, 0.0
        if self.phase == 2 and self.t > 0.05 * n + 0.4: self.timer.stop(); self.hide(); self.done.emit(); return
        self.update()
    def mousePressEvent(self, e):
        if self.phase == 1: self.phase, self.t = 2, 0.0; self.absorbing.emit()   # 누르면 캐릭터에게 좌르륵
    def paintEvent(self, _):
        p = QPainter(self)
        for i, c in enumerate(self.colors):
            tg = self.tg[i]
            if self.phase == 0:
                if self.t < 0.05 * i: continue
                k = ease_out(clamp((self.t - 0.05 * i) / 0.3)); pos = self.src + (tg - self.src) * k; size = 4 + (self.TOK - 4) * k
            elif self.phase == 1: pos, size = tg, self.TOK
            else: k = ease_in(clamp((self.t - 0.05 * i) / 0.4)); pos = tg + (self.dst - tg) * k; size = self.TOK * (1 - k)
            if size < 1: continue
            r = QRectF(pos.x() - size / 2, pos.y() - size / 2, size, size)
            p.setPen(QPen(QColor("#999"), 1)); p.setBrush(gray(c)); p.drawRect(r)
            if size >= 22: p.setPen(QColor(fg_for(c))); p.drawText(r, Qt.AlignCenter, str(c + 1))   # 몇 번 색인지

class ShapePicker(QWidget):                    # 부화 직후 단 한 번, 처음 모양 고르기
    picked = Signal(str)
    def __init__(self, parent):
        super().__init__(parent); page(self); self.hide(); self.rects = {}; self.imgs = {}
        for n, idx in SHAPES.items():
            img = QImage(SIZE, SIZE, QImage.Format_ARGB32); img.fill(0)
            for i in idx: img.setPixelColor(i % SIZE, i // SIZE, gray(BASE_COLOR))
            self.imgs[n] = img
    def start(self): self.setGeometry(0, 0, W, H); self.raise_(); self.show()
    def paintEvent(self, _):
        p = QPainter(self); p.setPen(QColor("#aaa")); p.drawText(QRectF(0, 50, W, 24), Qt.AlignCenter, "처음 모양을 골라주세요")
        for j, (n, img) in enumerate(self.imgs.items()):
            r = QRectF(8 + j * 70, 120, 64, 64); self.rects[n] = r; p.drawImage(r, img)
    def mousePressEvent(self, e):
        for n, r in self.rects.items():
            if r.contains(e.position()): self.hide(); self.picked.emit(n); return

# ---------------- 부화 연출 (64x64 격자, 칸 5px) ----------------
class HatchAnim(QWidget):                        # 메인 창 안에서 바로 재생 (화면의 글자는 모두 가려짐)
    done = Signal()
    S, OX, OY = 4, 46, 85                        # 아트 픽셀 4px, 메인 화면의 알 위치와 동일
    CRACK = [(16,6),(15,7),(15,8),(16,9),(17,10),(17,11),(16,12),(15,13),(15,14),(16,15),(17,16),(18,17),(18,18),(17,19),(16,20),(15,21),(15,22),(16,23),(17,24)]
    def __init__(self, parent):
        super().__init__(parent); page(self); self.hide(); self.img = sprite_image(EGG_IDLE); self.t = 0.0; self.pieces = []; self.parts = []
        self.timer = QTimer(self); self.timer.timeout.connect(self.tick)
    def start(self, colors):
        groups = {}
        for y, row in enumerate(EGG_IDLE):
            for x, ch in enumerate(row):
                if ch != "0":
                    k = (int((math.atan2(y - 16, x - 16) + math.pi) / 6.2832 * 8) % 8, math.hypot(x - 16, y - 16) > 7)
                    groups.setdefault(k, []).append((x, y, int(ch, 16)))
        self.pieces = []
        for px in groups.values():
            cx, cy = sum(a[0] for a in px) / len(px), sum(a[1] for a in px) / len(px)
            ang, sp = math.atan2(cy - 16, cx - 16), random.uniform(16, 30)
            self.pieces.append((px, math.cos(ang) * sp, math.sin(ang) * sp - 10))
        self.parts = [(random.uniform(0, 6.2832), random.uniform(8, 34), random.uniform(6, 20), c) for c in colors]
        self.t = 0.0; self.setGeometry(0, 0, W, H); self.raise_(); self.show(); self.timer.start(16)
    def tick(self):
        self.t += 0.016; self.update()
        if self.t > 4.2: self.timer.stop(); self.hide(); self.done.emit()
    def paintEvent(self, _):
        p = QPainter(self); S, t, ox, oy = self.S, self.t, self.OX, self.OY; p.setPen(Qt.NoPen)
        if t < 1.8:                                              # 흔들림 + 금
            jig = round(math.sin(t * 30) * min(1, t) * 1.5)
            p.drawImage(QRectF(ox + jig * S, oy, 32 * S, 32 * S), self.img)
            n = int(max(0, (t - 0.4) / 1.2) * len(self.CRACK)); p.setBrush(QColor(30, 30, 30))
            for x, y in self.CRACK[:n]: p.drawRect(ox + (jig + x) * S, oy + y * S, S, S)
            return
        tt = t - 1.8                                             # 파편 + 픽셀 파티클
        for px, vx, vy in self.pieces:
            dx, dy = round(vx * tt), round(vy * tt + 25 * tt * tt)
            for x, y, c in px: v = SPRITE_GRAYS[c - 1]; p.setBrush(QColor(v, v, v)); p.drawRect(ox + (x + dx) * S, oy + (y + dy) * S, S, S)
        p.setPen(QPen(QColor("#777"), 1))
        for a, v, up, c in self.parts:
            x = 16 + math.cos(a) * v * tt; y = 14 + math.sin(a) * v * tt - up * tt + 22 * tt * tt
            p.setBrush(gray(c)); p.drawRect(ox + int(x) * S, oy + int(y) * S, 2 * S, 2 * S)

# ---------------- 캐릭터 편집 (별도 창) ----------------
class GridCanvas(QWidget):
    CELL = 16
    def __init__(self, ed): super().__init__(); self.ed = ed; self.setFixedSize(SIZE * self.CELL, SIZE * self.CELL)
    def paintEvent(self, _):
        p = QPainter(self); c = self.CELL; p.fillRect(self.rect(), QColor("#1E1E1E"))      # 앱 배경과 동일
        for i, v in enumerate(self.ed.grid):
            if v >= 0: p.fillRect((i % SIZE) * c, (i // SIZE) * c, c, c, gray(v))
        p.setPen(QPen(QColor(255, 255, 255, 20)))                                          # 그리드
        for k in range(SIZE + 1): p.drawLine(k * c, 0, k * c, SIZE * c); p.drawLine(0, k * c, SIZE * c, k * c)
        f = p.font(); f.setPixelSize(14); p.setFont(f); p.setPen(QColor(255, 255, 255, 60))      # 정품 인증 안내문처럼 은은하게
        p.drawText(QRectF(10, 8, 320, 60), Qt.AlignLeft | Qt.AlignTop, f"{MOD}+Z  실행취소\n{MOD}+Y  다시실행\n{MOD}+Backspace  전체 비우기")
    def _apply(self, e, erase):
        x, y = int(e.position().x()) // self.CELL, int(e.position().y()) // self.CELL
        if 0 <= x < SIZE and 0 <= y < SIZE and self.ed.set_cell(y * SIZE + x, erase): self.update()
    def mousePressEvent(self, e): self.ed.begin(); self._apply(e, e.button() == Qt.RightButton)
    def mouseMoveEvent(self, e):
        if e.buttons(): self._apply(e, bool(e.buttons() & Qt.RightButton))
    def mouseReleaseEvent(self, e): self.ed.end()

class EditorDialog(QDialog):
    def __init__(self, game, parent=None):
        super().__init__(parent); self.game = game; self.sfx = getattr(parent, "sfx", None); self.setWindowTitle("그림몬 성형")
        self.grid = list(game.s["grid"]); self.owned = game.s["owned"]; self.used = [0] * 16
        for v in self.grid:
            if v >= 0: self.used[v] += 1
        self.color, self.erase, self.undo, self.redo, self._snap = 15, False, [], [], None
        root = QVBoxLayout(self); root.setSpacing(8)
        top = QHBoxLayout(); top.setSpacing(0); self.canvas = GridCanvas(self); top.addWidget(self.canvas)
        pal = QVBoxLayout(); pal.setSpacing(0); self.btns = []                # 그리드 바로 옆, 1:1 네모 17개 (마지막 = 지우개)
        for i in range(17):
            b = QPushButton("X" if i == 16 else ""); b.setFixedSize(30, 30)
            b.clicked.connect(self.pick_erase if i == 16 else (lambda _=False, i=i: self.pick(i))); pal.addWidget(b); self.btns.append(b)
        pal.addStretch(); top.addLayout(pal); top.addStretch(); root.addLayout(top)
        bot = QHBoxLayout(); bot.setSpacing(8)                                # [취소][저장] 2분할
        no = QPushButton("취소"); no.setFixedHeight(30); no.clicked.connect(self.reject)
        ok = QPushButton("저장"); ok.setFixedHeight(30); ok.clicked.connect(self.save); ok.setStyleSheet("background:#e6e6e6;color:#1E1E1E;border:none;")
        bot.addWidget(no, 1); bot.addWidget(ok, 1); root.addLayout(bot)
        for keys, fn in (("Ctrl+Z", self.do_undo), ("Ctrl+Y", self.do_redo), ("Ctrl+Backspace", self.clear)):   # 맥에서는 Cmd 로 동작
            QShortcut(QKeySequence(keys), self).activated.connect(fn)
        self.refresh()
    def refresh(self):
        for i, b in enumerate(self.btns[:16]):
            sel = (i == self.color and not self.erase); b.setText(str(self.owned[i] - self.used[i]))
            b.setStyleSheet(f"background:{gray(i).name()};color:{fg_for(i)};border:{3 if sel else 1}px solid {'#e33' if sel else '#444'};font-size:13px;padding:0;")
        self.btns[16].setStyleSheet(f"background:#2a2a2a;color:#ccc;border:{3 if self.erase else 1}px solid {'#e33' if self.erase else '#444'};padding:0;")
    def pick(self, i): self.color, self.erase = i, False; self.refresh()
    def pick_erase(self): self.erase = True; self.refresh()
    def begin(self): self._snap = list(self.grid)
    def end(self):
        if self._snap is not None and self._snap != self.grid: self.undo.append(self._snap); self.redo.clear()
        self._snap = None
    def set_cell(self, idx, erase):
        old = self.grid[idx]
        if erase or self.erase:
            if old < 0: return False
            self.used[old] -= 1; self.grid[idx] = EMPTY
        else:
            if old == self.color or self.owned[self.color] - self.used[self.color] <= 0: return False
            if old >= 0: self.used[old] -= 1
            self.grid[idx] = self.color; self.used[self.color] += 1
        if self.sfx: self.sfx.play("beep")
        self.refresh(); return True
    def _restore(self, g):
        self.grid = g; self.used = [0] * 16
        for v in g:
            if v >= 0: self.used[v] += 1
        self.canvas.update(); self.refresh()
    def do_undo(self):
        if self.undo: self.redo.append(list(self.grid)); self._restore(self.undo.pop())
    def do_redo(self):
        if self.redo: self.undo.append(list(self.grid)); self._restore(self.redo.pop())
    def clear(self): self.undo.append(list(self.grid)); self.redo.clear(); self._restore([EMPTY] * (SIZE * SIZE))
    def save(self): self.game.set_character(self.grid, self.game.s["name"]); self.game.save(); self.accept()

# ---------------- 페이지들 ----------------
class HoverCell(QLabel):
    clicked = Signal(int)
    def __init__(self, parent, i): super().__init__(parent); self.i = i; self.a = self.b = ""; self.setAlignment(Qt.AlignCenter)
    def enterEvent(self, e): self.setText(self.b)             # 호버: 색 코드
    def leaveEvent(self, e): self.setText(self.a)             # 평소: 남은/수집
    def mousePressEvent(self, e): self.clicked.emit(self.i)

class InventoryPage(QWidget):
    def __init__(self, win):
        super().__init__(win); page(self); self.win = win; self.t = 0.0
        b = QPushButton("<", self); b.setObjectName("back"); b.setGeometry(6, 6, 32, 32); b.clicked.connect(win.back_inv)
        self.cells = []
        for i in range(16):
            l = HoverCell(self, i); l.setGeometry(8 + (i % 4) * 52, 50 + (i // 4) * 52, 46, 46); l.clicked.connect(self.open_color); self.cells.append(l)
        d = self.det = QWidget(self); page(d); d.setGeometry(0, 0, W, H); d.hide()            # 마왕 상세
        db = QPushButton("<", d); db.setObjectName("back"); db.setGeometry(6, 6, 32, 32); db.clicked.connect(self.back_color)
        self.sw = QLabel(d)
        self.title = QLabel(d); self.title.setAlignment(Qt.AlignCenter); self.title.setGeometry(8, 94, 204, 40)
        self.sub = QLabel(d); self.sub.setAlignment(Qt.AlignCenter); self.sub.setGeometry(8, 134, 204, 18); self.sub.setStyleSheet("color:#888;font-size:12px;")
        self.story = QLabel(); self.story.setWordWrap(True); self.story.setAlignment(Qt.AlignTop | Qt.AlignLeft); self.story.setStyleSheet("color:#cfcfcf;font-size:14px;")
        self.sa = QScrollArea(d); self.sa.setGeometry(8, 158, 204, 156); self.sa.setWidgetResizable(True); self.sa.viewport().setStyleSheet("background:#1E1E1E;"); self.sa.setWidget(self.story)
        self.tm = QTimer(self); self.tm.timeout.connect(self.float_); self.anim = None
    def refresh(self):
        owned, placed = self.win.game.s["owned"], self.win.game.placed()
        for i, l in enumerate(self.cells):
            l.a = f"{owned[i] - placed[i]}/{owned[i]}"; l.b = f"{PALETTE[i]:02X}" * 3; l.setText(l.a)   # 남은 / 수집
            l.setStyleSheet(f"background:{gray(i).name()};color:{fg_for(i)};border:1px solid #555;font-size:12px;")
    def open_color(self, i):
        self.win.sfx.play("tap_up"); n, name, race, text = LORE[i]
        self.title.setText(f"제{n}대 마왕\n'{name}'"); self.sub.setText(f"#{PALETTE[i]:02X}" + f"{PALETTE[i]:02X}" * 2 + f" · {race}"); self.story.setText(text)
        self.sw.setStyleSheet(f"background:{gray(i).name()};border:1px solid #666;")
        for w in (self.title, self.sub, self.sa): w.hide()
        self.det.show(); self.det.raise_(); c = self.cells[i].geometry(); self.sw.setGeometry(c); self.sw.show()
        a = QPropertyAnimation(self.sw, b"geometry", self); a.setDuration(260); a.setStartValue(c); a.setEndValue(QRect(74, 18, 72, 72))
        a.setEasingCurve(QEasingCurve.OutBack); a.finished.connect(self._shown); self.anim = a; a.start()   # 픽셀이 커지며
    def _shown(self):
        for w in (self.title, self.sub, self.sa): w.show()
        self.t = 0.0; self.tm.start(50)
    def float_(self):                                                                                       # 살짝씩 움직임
        self.t += 0.05; self.sw.move(74 + int(math.sin(self.t * 1.7) * 3), 18 + int(math.sin(self.t * 2.3) * 4))
    def back_color(self): self.win.sfx.play("tap_down"); self.close_color()
    def close_color(self): self.tm.stop(); self.det.hide()

class InputTestDialog(QDialog):
    def __init__(self, win):
        super().__init__(win); self.win, self.sum = win, 0.0; self.setWindowTitle("입력 테스트"); self.setFixedSize(300, 190)
        lay = QVBoxLayout(self); self.status = QLabel(); self.box = QLabel("이 안에서 펜/마우스로\n선을 그어보세요"); self.box.setAlignment(Qt.AlignCenter)
        self.box.setMinimumHeight(90); self.box.setStyleSheet("border:2px dashed #666;")
        c = QPushButton("닫기"); c.clicked.connect(self.accept)
        for w in (self.status, self.box, c): lay.addWidget(w)
        win.bus.moved.connect(self.on_moved); win.bus.test_on = True
        self.tm = QTimer(self); self.tm.timeout.connect(self.upd); self.tm.start(500); self.upd()
    def on_moved(self, cm): self.sum += cm; self.box.setText(f"입력 감지됨\n{self.sum:.1f} cm")
    def upd(self):
        self.status.setText({"ok": "입력 감지: 정상", "starting": "입력 감지: 시작 중…", "permission": "입력 모니터링 권한이 필요해요\n(시스템 설정 → 개인정보 보호 및 보안)",
                             "error": "입력 감지 모듈 오류"}.get(self.win.tracker.status, ""))
    def done(self, r):
        self.win.bus.test_on = False
        try: self.win.bus.moved.disconnect(self.on_moved)
        except Exception: pass
        super().done(r)

class SettingsPage(QWidget):
    def __init__(self, win):
        super().__init__(win); page(self); self.win = win; self.g = win.game
        b = QPushButton("<", self); b.setObjectName("back"); b.setGeometry(6, 6, 32, 32); b.clicked.connect(self.save)   # < = 저장 후 닫기
        lay = QVBoxLayout(self); lay.setContentsMargins(12, 44, 12, 8); lay.setSpacing(5)
        lay.addWidget(QLabel("기기"))
        self.maker, self.model = QComboBox(), QComboBox()
        for c in (self.maker, self.model):
            c.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon); c.setMinimumContentsLength(12); c.view().setMinimumWidth(300); lay.addWidget(c)
        self.maker.addItems(list(DEVICE_DB) + [OTHER]); self.maker.currentTextChanged.connect(self.fill)
        r0 = QHBoxLayout(); t = QPushButton("입력 테스트"); t.clicked.connect(lambda: InputTestDialog(win).exec())
        self.nb = QPushButton("이름 변경"); self.nb.clicked.connect(lambda: win.ask_name(self.g.s["name"])); r0.addWidget(t); r0.addWidget(self.nb); lay.addLayout(r0)
        self.top, self.tray = QCheckBox("항상 위"), QCheckBox("트레이 최소화"); lay.addWidget(self.top); lay.addWidget(self.tray)
        row = QHBoxLayout(); u = QPushButton("업데이트 확인"); u.clicked.connect(win.check_update_manual)
        q = QPushButton("종료"); q.clicked.connect(win.quit_app); row.addWidget(u); row.addWidget(q); lay.addLayout(row)
        if getattr(config, "DEBUG", True):                                   # 배포 전 config.py 에 DEBUG = False
            d = QPushButton("[디버그] 알부터 다시"); d.clicked.connect(self.reset_all); lay.addWidget(d)
        lay.addStretch()
        v = QLabel(f"그림몬 v{config.VERSION}"); v.setAlignment(Qt.AlignCenter); v.setStyleSheet("color:#777;"); lay.addWidget(v)
    def fill(self, maker):
        self.model.clear()
        if maker in DEVICE_DB: self.model.addItems([m[0] for m in DEVICE_DB[maker]])
        self.model.addItem(SCREEN)
    def load(self):
        d = self.g.s["device"] or {}
        if d.get("maker"): self.maker.setCurrentText(d["maker"])
        self.fill(self.maker.currentText())
        if d.get("model"): self.model.setCurrentText(d["model"])
        self.nb.setEnabled(self.g.s["hatched"])
        self.top.setChecked(self.g.s["always_on_top"]); self.tray.setChecked(self.g.s["close_to_tray"])
    def reset_all(self):
        if QMessageBox.question(self, "리셋", "알부터 완전히 다시 시작할까요?\n(기기·프로그램 설정은 유지)") != QMessageBox.Yes: return
        self.g.reset_progress(); self.g.save(); self.win.after_reset()
    def save(self):
        maker, model = self.maker.currentText(), self.model.currentText()
        spec = next((m for m in DEVICE_DB.get(maker, []) if m[0] == model), None)
        s = self.g.s; s["device"] = {"maker": maker, "model": model, "w_mm": spec[1] if spec else 0, "h_mm": spec[2] if spec else 0}
        s["setup_done"] = True; s["always_on_top"] = self.top.isChecked(); s["close_to_tray"] = self.tray.isChecked(); self.g.dirty = True
        self.g.save(); self.win.apply_flags(); self.win.back_settings()

class RankRow(QWidget):
    clicked = Signal()
    def mousePressEvent(self, e): self.clicked.emit()

class RankDetail(QWidget):                       # 던전 랭크: 선택한 사람의 캐릭터 크게 보기
    def __init__(self, parent):
        super().__init__(parent); self.win = parent.win; page(self); self.setGeometry(0, 0, W, H); self.hide(); self.d = None; self.rank = 0; self._img = None
        b = QPushButton("<", self); b.setObjectName("back"); b.setGeometry(6, 6, 32, 32); b.clicked.connect(self._back)
        self.tm = QTimer(self); self.tm.timeout.connect(self.update)
    def show_row(self, rank, d): self.win.sfx.play("tap_up"); self.d, self.rank = d, rank; self._img = grid_image(board.dec(d["grid"])); self.show(); self.raise_(); self.tm.start(50)
    def hideEvent(self, e):
        if hasattr(self, "tm"): self.tm.stop()          # 생성 중 hide() 호출 시 타이머가 아직 없음
    def _back(self): self.win.sfx.play("tap_down"); self.hide()
    def paintEvent(self, _):
        if not self.d: return
        p = QPainter(self); t = time.time(); d = self.d; sc = 5
        p.setPen(QColor("#9a9a9a")); p.drawText(QRectF(44, 6, 170, 32), Qt.AlignVCenter | Qt.AlignLeft, f"{self.rank}위")
        bx, by = int(math.sin(t * 2) * 2), int(-abs(math.sin(t * 3)) * 4)
        p.setPen(Qt.NoPen); p.setBrush(QColor(0, 0, 0, 70)); p.drawEllipse(QPointF(W / 2, 214), 48, 4)
        p.drawImage(QRectF((W - 32 * sc) // 2 + bx, 52 + by, 32 * sc, 32 * sc), self._img)
        f = p.font(); f.setPixelSize(24); p.setFont(f); p.setPen(QColor("#ffffff")); p.drawText(QRectF(0, 228, W, 30), Qt.AlignCenter, d["name"])
        f.setPixelSize(16); p.setFont(f); p.setPen(QColor("#9a9a9a")); p.drawText(QRectF(0, 262, W, 22), Qt.AlignCenter, f'전체 {d["cm"] / 100:.2f}m')
        if d.get("day") == datetime.date.today().isoformat(): p.drawText(QRectF(0, 284, W, 22), Qt.AlignCenter, f'오늘 {(d.get("today") or 0) / 100:.2f}m')

class LeaderboardPage(QWidget):
    res = Signal(object)
    def __init__(self, win):
        super().__init__(win); page(self); self.win = win; self.tab = "all"
        b = QPushButton("<", self); b.setObjectName("back"); b.setGeometry(6, 6, 32, 32); b.clicked.connect(win.back_lb)
        t = QLabel("던전 랭크", self); t.setGeometry(44, 6, 170, 32); t.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.tabs = {}
        for j, (k, txt) in enumerate((("all", "전체"), ("today", "오늘"))):
            tb = QPushButton(txt, self); tb.setGeometry(12 + j * 100, 40, 96, 26); tb.clicked.connect(lambda _=False, k=k: self.set_tab(k)); self.tabs[k] = tb
        self.msg = QLabel(self); self.msg.setGeometry(12, 68, 196, 30); self.msg.setWordWrap(True); self.msg.setStyleSheet("color:#888;font-size:12px;")
        self.area = QScrollArea(self); self.area.setGeometry(6, 100, 208, 214); self.area.setWidgetResizable(True); self.area.viewport().setStyleSheet("background:#1E1E1E;")
        self.detail = RankDetail(self); self.res.connect(self.show_res); self._reset(); self._style()
    def _style(self):
        for k, tb in self.tabs.items(): tb.setStyleSheet("background:#e6e6e6;color:#1E1E1E;border:none;" if k == self.tab else "")
    def _reset(self):
        self.inner = QWidget(); page(self.inner); self.vl = QVBoxLayout(self.inner); self.vl.setContentsMargins(0, 0, 0, 0); self.vl.setSpacing(2); self.vl.setAlignment(Qt.AlignTop)
        self.area.setWidget(self.inner)
    def open(self): self.detail.hide(); self.tab = "all"; self._style(); self.load(True)      # 열 때 내 기록 업로드
    def set_tab(self, k): self.tab = k; self._style(); self.load(False)
    def load(self, submit):
        g = self.win.game; s = g.s; tab = self.tab
        snap = dict(uid=s["uid"], name=s["name"] or "그림몬", total_cm=s["total_cm"], grid=list(s["grid"]), day=datetime.date.today().isoformat(), today=g.today_cm())
        self.msg.setText("불러오는 중…"); self._reset()
        def run():
            try: self.res.emit(("ok", tab, board.sync(snap, tab, submit)))
            except Exception as e: self.res.emit(("err", str(e)))
        threading.Thread(target=run, daemon=True).start()
    def show_res(self, r):
        if r[0] == "err": print("rank error:", r[1]); self.msg.setText("서버에 연결하지 못했어요\n" + friendly(r[1])); return
        if r[1] != self.tab: return                         # 탭을 바꾼 뒤 늦게 온 응답은 무시
        self.msg.setText("" if r[2] else "아직 기록이 없어요"); self._reset(); me = self.win.game.s["uid"]
        for i, d in enumerate(r[2][:30]):
            w = RankRow(); h = QHBoxLayout(w); h.setContentsMargins(2, 2, 2, 2); h.setSpacing(6)
            col = "#ffffff" if d["uid"] == me else "#9a9a9a"
            rk = QLabel(str(i + 1)); rk.setFixedWidth(20); th = QLabel(); th.setFixedSize(32, 32)
            th.setPixmap(QPixmap.fromImage(grid_image(board.dec(d["grid"]))))
            val = d.get("today") if self.tab == "today" else d["cm"]
            nm, ds = QLabel(d["name"]), QLabel(f'{(val or 0) / 100:.2f}m')
            for x in (rk, nm, ds): x.setStyleSheet(f"color:{col};")
            h.addWidget(rk); h.addWidget(th); h.addWidget(nm, 1); h.addWidget(ds); w.setFixedHeight(38)
            w.clicked.connect(lambda i=i, d=d: self.detail.show_row(i + 1, d)); self.vl.addWidget(w)

class ClickLabel(QLabel):
    clicked = Signal()
    def mousePressEvent(self, e): self.clicked.emit()

class GraphPage(QWidget):                       # 최근 7일 일별 거리 (픽셀아트 막대)
    P = 4                                       # 아트 픽셀 1칸 = 4px
    CUR = ("#ffffff", "#f0f0f0", "#d8d8d8", "#b8b8b8", "#8f8f8f")      # 오늘: 밝은 음영 (왼쪽 빛 → 오른쪽 그늘)
    OLD = ("#a8a8a8", "#8c8c8c", "#767676", "#606060", "#4a4a4a")
    def __init__(self, win):
        super().__init__(win); page(self); self.win = win; self.setGeometry(0, -GH, W, GH); self.hide()
    def mousePressEvent(self, e): self.win.close_graph()
    def paintEvent(self, _):
        p = QPainter(self); P = self.P; daily = self.win.game.s["daily"]; today = datetime.date.today()
        days = [today - datetime.timedelta(days=i) for i in range(6, -1, -1)]
        vals = [daily.get(d.isoformat(), 0.0) / 100 for d in days]; top = max(max(vals), 0.01)
        base, hmax = GH - 44, GH - 120
        p.setPen(QPen(QColor(255, 255, 255, 16), 1))                      # 맨 아래 레이어: 옅은 그리드
        for y in range(base, 44, -20): p.drawLine(12, y, W - 12, y)
        for i in range(8): x = 14 + i * 28; p.drawLine(x, 44, x, base)
        p.setPen(QPen(QColor("#4a4a4a"), 1)); p.drawLine(12, base, W - 12, base)
        f = p.font(); f.setPixelSize(16); p.setFont(f); p.setPen(QColor("#9a9a9a")); p.drawText(QRectF(0, 12, W, 22), Qt.AlignCenter, "최근 7일")
        rows_max = hmax // P
        for i, (d, v) in enumerate(zip(days, vals)):
            x0 = 16 + i * 28
            if v > 0:                                                       # 기록 없는 날은 아무것도 그리지 않음
                n = max(2, round(rows_max * v / top)); pal = [QColor(c) for c in (self.CUR if i == 6 else self.OLD)]
                for r in range(n):                                          # r=0 이 맨 위줄
                    y = base - (n - r) * P
                    for c in (range(1, 4) if r == 0 else range(5)):         # 윗부분 둥글게
                        p.fillRect(x0 + c * P, y, P, P, pal[c])
                f.setPixelSize(12); p.setFont(f); p.setPen(QColor("#bdbdbd"))
                p.drawText(QRectF(x0 - 4, base - n * P - 18, 28, 16), Qt.AlignCenter, f"{v:.1f}m" if v < 10 else f"{v:.0f}m")
            f.setPixelSize(14); p.setFont(f); p.setPen(QColor("#8a8a8a")); p.drawText(QRectF(x0 - 4, base + 6, 28, 18), Qt.AlignCenter, str(d.day))

# ---------------- 메인 창 ----------------
class MainWindow(QWidget):
    def __init__(self, game, tracker, bus, updater, app):
        super().__init__(); self.game, self.tracker, self.bus, self.updater, self.app = game, tracker, bus, updater, app
        self.busy = self.sliding = self.menu_open = False; self._manual = False; self._notified = set(); self._gift_note = False; self.mt = 0.0; self.sfx = Sfx(); self._pick_checked = False; self._was_ready = game.s["gift_ready"]; self.graph_open = False
        page(self); self.setWindowTitle("그림몬"); self.setFixedSize(W, H); self.setWindowIcon(egg_icon())
        h = self.home = QWidget(self); page(h); h.setGeometry(0, 0, W, H); self.cur = h
        self.dist = ClickLabel(h); self.dist.setAlignment(Qt.AlignHCenter | Qt.AlignTop); self.dist.setStyleSheet("font-size:38px;padding-top:5px;"); self.dist.setCursor(Qt.PointingHandCursor); self.dist.clicked.connect(self.toggle_graph)
        self.view = CharView(game, h); self.view.clicked.connect(self.toggle_menu)
        self.today = ClickLabel(h); self.today.setAlignment(Qt.AlignCenter); self.today.setStyleSheet("color:#8a8a8a;font-size:14px;"); self.today.setCursor(Qt.PointingHandCursor); self.today.clicked.connect(self.toggle_graph)
        self.name = QLabel(h); self.name.setAlignment(Qt.AlignCenter); self.name.setStyleSheet("font-size:19px;")
        self.gauge = PixelGauge(game, h); self.gauge.clicked.connect(self.claim)
        self.mbox = QWidget(h); self.mbtn = {}
        for key, text, fn in (("edit", "그림몬 성형", self.edit), ("inv", "수집 픽셀", self.open_inv),
                              ("lb", "던전 랭크", self.open_lb), ("set", "설정", self.open_settings)):
            b = QPushButton(text, self.mbox); b.setObjectName("mi"); b.clicked.connect(fn); self.mbtn[key] = b
        self.badge = QLabel(self.mbox); self.badge.setAlignment(Qt.AlignCenter); self.badge.setFixedSize(22, 18)
        self.badge.setStyleSheet("background:#eeeeee;color:#1E1E1E;"); self.badge.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.fx = {}
        for w in (self.dist, self.today, self.name, self.gauge, self.mbox):
            e = QGraphicsOpacityEffect(w); w.setGraphicsEffect(e); self.fx[w] = e
        self.mt_anim = QVariantAnimation(self); self.mt_anim.setDuration(240); self.mt_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.mt_anim.valueChanged.connect(self.layout_home); self.layout_home(0.0)
        self.inv, self.setp, self.lb = InventoryPage(self), SettingsPage(self), LeaderboardPage(self)
        self.graph = GraphPage(self)
        for p in (self.inv, self.setp, self.lb): p.setGeometry(W, 0, W, H); p.hide()
        self.overlay = ClaimOverlay(self); self.overlay.done.connect(lambda: setattr(self, "busy", False)); self.overlay.absorbing.connect(lambda: self.sfx.play("tap_up"))
        self.picker = ShapePicker(self); self.picker.picked.connect(self.on_shape); self.hatch_anim = HatchAnim(self); self.hatch_anim.done.connect(self.after_hatch)
        self.tray = QSystemTrayIcon(egg_icon(), self); tm = _menu(self)
        self.tray.setContextMenu(tm); self.tray.activated.connect(lambda r: self.show_main() if r == QSystemTrayIcon.Trigger else None); self.tray.show()
        self.poll = QTimer(self); self.poll.timeout.connect(self.refresh); self.poll.start(250)
        self.tick = QTimer(self); self.tick.timeout.connect(self._repaint)
        self.saver = QTimer(self); self.saver.timeout.connect(game.save); self.saver.start(config.SAVE_INTERVAL_MS)
        self.updater.done.connect(self.on_update); QTimer.singleShot(5000, self.updater.check)
        self.upt = QTimer(self); self.upt.timeout.connect(self.updater.check); self.upt.start(config.UPDATE_CHECK_HOURS * 3600 * 1000)
        self.apply_flags()
    def showEvent(self, e): self.tick.start(50)         # 보일 때만 20fps
    def hideEvent(self, e): self.tick.stop()
    def _repaint(self):
        if self.cur is self.home: self.view.update(); self.gauge.update()
    def apply_flags(self):
        vis = self.isVisible(); self.setWindowFlag(Qt.WindowStaysOnTopHint, self.game.s["always_on_top"])
        if vis: self.show()
    def show_main(self): self.show(); self.raise_(); self.activateWindow()
    # --- 홈 레이아웃 (t: 0=홈, 1=메뉴) ---
    def layout_home(self, t):
        t = float(t); self.mt = t; L = lambda a, b: int(a + (b - a) * t)
        self.dist.setGeometry(0, L(0, -70), W, 68); self.today.setGeometry(0, L(42, -60), W, 20); self.view.setGeometry(0, L(68, 6), W, L(162, 150))
        self.gauge.setGeometry(10, L(246, -60), 200, 38); self.name.setGeometry(0, L(280, -60), W, 28)
        self.mbox.setGeometry(0, 164, W, 150)
        for w in (self.dist, self.today, self.name, self.gauge): self.fx[w].setOpacity(1 - t)
        self.fx[self.mbox].setOpacity(t); self.mbox.setVisible(t > 0.02)
    def toggle_menu(self):
        if self.sliding or self.busy: return
        self.menu_open = not self.menu_open; self.refresh(); self.sfx.play("tap_up" if self.menu_open else "tap_down")
        self.mt_anim.stop(); self.mt_anim.setStartValue(self.mt); self.mt_anim.setEndValue(1.0 if self.menu_open else 0.0); self.mt_anim.start()
    def refresh(self):
        s = self.game.s; hat = s["hatched"]
        if self.graph.isVisible(): self.graph.update()
        self.dist.setText(fmt_distance(s["total_cm"], hat)); self.name.setText((s["name"] or "그림몬") if hat else "알")
        self.today.setText(f"오늘 {self.game.today_cm() / 100:.2f}m" if hat else "")
        self.gauge.setVisible(hat); self.gauge.setCursor(Qt.PointingHandCursor if s["gift_ready"] else Qt.ArrowCursor)
        y = 0
        for k in ("edit", "inv", "lb", "set"):
            b = self.mbtn[k]; show = hat or k == "set"; b.setVisible(show)
            if show: b.setGeometry(0, y, W, 34); y += 36
        n = s["unseen"]; self.badge.setVisible(hat and n > 0); self.badge.setText("9+" if n > 9 else str(n)); self.badge.move((W + self.mbtn["edit"].fontMetrics().horizontalAdvance("그림몬 성형")) // 2 + 8, 8)
        if s["gift_ready"] and not self._was_ready: self.sfx.play("ready")
        self._was_ready = s["gift_ready"]
        if s["gift_ready"] and not self.isVisible() and not self._gift_note: self._gift_note = True; self.tray.showMessage("그림몬", "선물이 도착했어요!")
        if not s["gift_ready"]: self._gift_note = False
        if not hat and s["total_cm"] >= config.HATCH_CM and not self.busy: self.hatch()
        if hat and not s["shape_done"] and not self._pick_checked and not self.busy:
            self._pick_checked = True
            if all(v < 0 for v in s["grid"]): self.busy = True; self.picker.start()
    # --- 슬라이드 전환 ---
    def slide(self, frm, to, dx, dy):
        if self.sliding: return
        self.sliding = True; self.sfx.play("tap_up" if frm is self.home else "tap_down"); to.setGeometry(dx * W, dy * H, W, H); to.show(); to.raise_(); self.overlay.raise_()
        g = QParallelAnimationGroup(self); self._g = g
        for w, end in ((frm, (-dx * W, -dy * H)), (to, (0, 0))):
            a = QPropertyAnimation(w, b"pos", self); a.setDuration(260); a.setEndValue(QPoint(*end))
            a.setEasingCurve(QEasingCurve.OutCubic); g.addAnimation(a)
        def fin(): frm.hide(); self.cur = to; self.sliding = False
        g.finished.connect(fin); g.start()
    def open_inv(self): self.inv.refresh(); self.inv.close_color(); self.slide(self.home, self.inv, 1, 0)
    def back_inv(self): self.home.show(); self.slide(self.inv, self.home, -1, 0)
    def open_lb(self): self.lb.open(); self.slide(self.home, self.lb, 1, 0)
    def back_lb(self): self.home.show(); self.slide(self.lb, self.home, -1, 0)
    def open_settings(self): self.setp.load(); self.slide(self.home, self.setp, 0, 1)
    def back_settings(self): self.home.show(); self.slide(self.setp, self.home, 0, -1)
    def start_setup(self):                              # 최초 실행: 설정 화면부터
        self.setp.load(); self.home.hide(); self.setp.setGeometry(0, 0, W, H); self.setp.show(); self.cur = self.setp
    # --- 동작 ---
    def hatch(self):
        self.busy = True; self.show_main(); colors = self.game.hatch(); self.game.save()
        try: self.hatch_anim.start(colors)                   # 이 창 안에서 바로 재생. 연출 오류가 나도 지급은 이미 끝남
        except Exception as e: print("hatch anim:", e); self.after_hatch()
    def after_hatch(self):                                    # 연출 끝 → 이름 짓기 → 모양 고르기 → 성형
        self.ask_name(""); self.picker.start()
    def ask_name(self, initial=""):
        d = QInputDialog(self); d.setWindowTitle("그림몬"); d.setLabelText("이름을 입력해주세요"); d.setTextValue(initial)
        d.setOkButtonText("확인"); d.setCancelButtonText("취소")
        if d.exec():
            n = d.textValue().strip()[:12]
            if n: self.game.s["name"] = n; self.game.dirty = True; self.game.save(); self.refresh()
    def claim(self):
        if self.busy or self.menu_open or self.sliding or not self.game.s["gift_ready"]: return
        colors = self.game.claim_gift(); self.game.save(); self.busy = True; self.sfx.play("pop")
        try:
            self.overlay.start(colors, self.gauge.mapTo(self, self.gauge.bar_center()), self.view.mapTo(self, self.view.rect().center()))
        except Exception as e: print("claim anim:", e); self.busy = False
    def toggle_graph(self):                       # 전체 화면이 내려가고 위에서 그래프가 내려옴 (거리는 하단에 남음)
        if self.sliding or self.busy or self.menu_open or self.cur is not self.home: return
        self.graph_open = not self.graph_open; self.sliding = True
        self.sfx.play("tap_up" if self.graph_open else "tap_down")
        if self.graph_open: self.graph.show(); self.graph.raise_(); self.overlay.raise_()
        g = QParallelAnimationGroup(self); self._g2 = g
        for w, y in ((self.home, GH if self.graph_open else 0), (self.graph, 0 if self.graph_open else -GH)):
            a = QPropertyAnimation(w, b"pos", self); a.setDuration(320); a.setEndValue(QPoint(0, y)); a.setEasingCurve(QEasingCurve.OutCubic); g.addAnimation(a)
        def fin():
            self.sliding = False
            if not self.graph_open: self.graph.hide()
        g.finished.connect(fin); g.start()
    def close_graph(self):
        if self.graph_open: self.toggle_graph()
    def on_shape(self, name):
        self.game.apply_shape(name); self.game.save(); self.busy = False; self.edit()
    def after_reset(self):
        self.menu_open = False; self.layout_home(0.0); self.refresh(); self.back_settings()
    def edit(self):
        self.game.s["unseen"] = 0; self.game.dirty = True; self.refresh(); EditorDialog(self.game, self).exec()
    def closeEvent(self, e):
        if self.game.s["close_to_tray"]:
            e.ignore(); self.hide()
            if not self.game.s["tray_hint_shown"]:
                self.game.s["tray_hint_shown"] = True; self.game.dirty = True
                self.tray.showMessage("그림몬", "트레이로 최소화했어요. 거리 측정은 계속됩니다.\n완전히 종료하려면 트레이 메뉴 → 종료")
        else: self.quit_app()
    def quit_app(self): self.game.save(); self.app.quit()
    def check_update_manual(self): self._manual = True; self.updater.check()
    def on_update(self, r):
        manual, self._manual = self._manual, False
        if not r["ok"]:
            if manual: QMessageBox.warning(self, "업데이트 확인", f"확인하지 못했어요.\n{r['err']}")
            return
        if r["newer"]:
            if r["tag"] in self._notified and not manual: return
            self._notified.add(r["tag"]); self.show_main()
            b = QMessageBox(self); b.setWindowTitle("새 버전이 나왔어요!"); b.setText(f"{r['tag']} 출시! (현재 {config.VERSION})\n\n{r['notes']}")
            go = b.addButton("다운로드 열기", QMessageBox.AcceptRole); b.addButton("나중에", QMessageBox.RejectRole); b.exec()
            if b.clickedButton() is go: webbrowser.open(r["url"])
        elif manual: QMessageBox.information(self, "업데이트 확인", "최신 버전이에요")

def _menu(win):
    from PySide6.QtWidgets import QMenu
    m = QMenu(); m.addAction("열기", win.show_main); m.addAction("종료", win.quit_app); return m
