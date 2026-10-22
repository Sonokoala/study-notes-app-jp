"""監視するフォルダを定期的に確認し、作業を順番待ちに入れる。

録画のフォルダ        : 新しい音声・動画・.txt が書き込み終わったら、1ファイルずつ処理する
スクリーンショットのフォルダ : N 分間新しい画像が増えなかったら、たまった画像をまとめて処理し、done\\<日時> に移す
フォルダを追加した時点ですでにあったファイルは処理しない。
"""
import datetime, json, os, shutil, threading, time
from . import config
from .pipeline import AUDIO_VIDEO, IMAGES

STATE = os.path.join(config.DIR, "processed.json")


def _load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"done": {}, "since": {}}


def _save_state(st):
    os.makedirs(config.DIR, exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def _ready(path, quiet_sec=60):
    """ファイルが完成しているか: しばらく書き込まれておらず、録画ソフトにロックされていない"""
    try:
        if time.time() - os.path.getmtime(path) < quiet_sec:
            return False
        with open(path, "rb+"):
            return True
    except OSError:
        return False


class Watcher:
    def __init__(self, get_cfg, submit, log, interval=30):
        self.get_cfg, self.submit, self.log, self.interval = get_cfg, submit, log, interval
        self.stop_evt = threading.Event()
        self.thread = None
        self.busy = set()
        self.failed = {}  # スクリーンショットのフォルダ -> 失敗したときの画像（画像が変わったら再試行）

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_evt.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self.log("フォルダの監視を始めました")

    def stop(self):
        self.stop_evt.set()
        self.log("フォルダの監視を止めました")

    @property
    def running(self):
        return bool(self.thread and self.thread.is_alive() and not self.stop_evt.is_set())

    def _run(self):
        while not self.stop_evt.is_set():
            try:
                self.scan()
            except Exception as e:
                self.log(f"監視中のエラー: {e}")
            self.stop_evt.wait(self.interval)

    def scan(self):
        cfg = self.get_cfg()
        st = _load_state()
        changed = False
        for w in cfg.get("watch", []):
            folder = w["path"]
            if not os.path.isdir(folder):
                continue
            if folder not in st["since"]:
                st["since"][folder] = time.time()
                changed = True
                continue
            since = st["since"][folder]
            files = [os.path.join(folder, n) for n in os.listdir(folder)]
            files = [p for p in files if os.path.isfile(p) and os.path.getctime(p) > since]
            if w.get("kind") == "screenshots":
                imgs = [p for p in files if os.path.splitext(p)[1].lower() in IMAGES]
                if not imgs or folder in self.busy or self.failed.get(folder) == set(imgs):
                    continue
                idle = cfg.get("screenshot_idle_min", 5) * 60
                if time.time() - max(os.path.getmtime(p) for p in imgs) < idle:
                    continue
                self._queue(w, "screenshots", imgs, folder, done_move=True)
            else:
                for p in files:
                    if os.path.splitext(p)[1].lower() not in AUDIO_VIDEO | {".txt"}:
                        continue
                    if p in st["done"] or p in self.busy or not _ready(p):
                        continue
                    st["done"][p] = time.time()
                    changed = True
                    self._queue(w, "recording", [p], p)
        if changed:
            _save_state(st)

    def _queue(self, w, kind, paths, key, done_move=False):
        self.busy.add(key)

        def finished(ok):
            if ok and done_move:
                dest = os.path.join(w["path"], "done", datetime.datetime.now().strftime("%Y-%m-%d_%H%M"))
                os.makedirs(dest, exist_ok=True)
                for p in paths:
                    shutil.move(p, dest)
            elif done_move:
                self.failed[key] = set(paths)
            self.busy.discard(key)

        self.submit(kind, paths, w.get("subject", ""), finished)
