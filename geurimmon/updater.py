import json, re, threading
from urllib.request import Request, urlopen
from PySide6.QtCore import QObject, Signal
from . import config
from .board import CTX

def _ver(s):
    return tuple(int(x) for x in re.findall(r"\d+", s)[:3]) or (0,)

class Updater(QObject):
    done = Signal(dict)

    def check(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        if config.GITHUB_OWNER == "YOUR_GITHUB_ID":
            self.done.emit({"ok": False, "err": "깃헙 주소가 아직 설정되지 않았어요 (geurimmon/config.py)"}); return
        url = f"https://api.github.com/repos/{config.GITHUB_OWNER}/{config.GITHUB_REPO}/releases/latest"
        try:
            req = Request(url, headers={"User-Agent": "Geurimmon", "Accept": "application/vnd.github+json"})
            d = json.load(urlopen(req, timeout=10, context=CTX))
            tag = d.get("tag_name", "")
            self.done.emit({"ok": True, "tag": tag, "url": d.get("html_url"),
                            "newer": _ver(tag) > _ver(config.VERSION),
                            "notes": (d.get("body") or "")[:400]})
        except Exception as e:
            self.done.emit({"ok": False, "err": str(e)})
