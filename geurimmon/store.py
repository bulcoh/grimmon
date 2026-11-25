import json, os, shutil
import sys
DIR = (os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Geurimmon") if sys.platform == "win32"
       else os.path.expanduser("~/Library/Application Support/Geurimmon"))
FILE = os.path.join(DIR, "save.json")

class Store:
    def __init__(self):
        os.makedirs(DIR, exist_ok=True)

    def load(self):
        for f in (FILE, FILE + ".bak"):
            try:
                with open(f, encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception:
                continue
        return None

    def save(self, state):
        tmp = FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False)
            fh.flush(); os.fsync(fh.fileno())
        if os.path.exists(FILE):
            shutil.copy2(FILE, FILE + ".bak")
        os.replace(tmp, FILE)
