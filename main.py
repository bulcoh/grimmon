import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from geurimmon.store import Store
from geurimmon.game import Game
from geurimmon.tracker import Tracker
from geurimmon.updater import Updater
from geurimmon.ui import MainWindow, Bus, load_theme

def main():
    app = QApplication(sys.argv); app.setQuitOnLastWindowClosed(False); load_theme(app)
    game = Game(Store()); bus = Bus(); updater = Updater()

    def on_move(cm):                       # 입력 스레드: 메모리 갱신만
        if bus.test_on: bus.moved.emit(cm)
        if not bus.app_active and game.s["setup_done"]:   # 그림몬 창 안의 드래그는 거리로 안 침
            game.add_distance(cm)

    tracker = Tracker(on_move, lambda: game.s["device"]); tracker.start()
    app.applicationStateChanged.connect(lambda st: setattr(bus, "app_active", st == Qt.ApplicationActive))
    win = MainWindow(game, tracker, bus, updater, app)
    app.aboutToQuit.connect(game.save)
    win.show()
    if not game.s["setup_done"]:
        win.start_setup()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
