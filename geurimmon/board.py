import json, os, ssl
from urllib.request import Request, urlopen
from . import config

def _ctx():                                   # 인증서: certifi → 맥 시스템 번들 → 기본값 순
    paths = []
    try:
        import certifi; paths.append(certifi.where())
    except Exception:
        pass
    paths += ["/etc/ssl/cert.pem", "/opt/homebrew/etc/ca-certificates/cert.pem", "/opt/homebrew/etc/openssl@3/cert.pem"]
    for p in paths:
        if os.path.exists(p):
            try: return ssl.create_default_context(cafile=p)
            except Exception: pass
    return None
CTX = _ctx()

def enc(grid): return "".join("." if v < 0 else "0123456789abcdef"[v] for v in grid)
def dec(s): return [-1 if c == "." else int(c, 16) for c in s]

def sync(snap, tab="all", submit=True):
    """submit=True 면 내 기록을 먼저 올린다. tab: all(전체) / today(오늘)."""
    url = getattr(config, "SERVER_URL", "").rstrip("/")
    if not url: raise RuntimeError("SERVER_URL 미설정")
    h = {"Content-Type": "application/json", "X-Key": getattr(config, "SERVER_KEY", ""), "User-Agent": "Geurimmon"}
    if submit:
        body = json.dumps({"uid": snap["uid"], "name": snap["name"], "cm": snap["total_cm"], "grid": enc(snap["grid"]),
                           "day": snap["day"], "today": snap["today"]}).encode()
        urlopen(Request(url + "/submit", body, h), timeout=8, context=CTX).read()
    return json.load(urlopen(Request(f"{url}/board?tab={tab}&day={snap['day']}", headers=h), timeout=8, context=CTX))
