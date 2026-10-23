"""設定は %APPDATA%\\StudyNotesJP\\config.json に保存する（API キーはこの PC の外に出ない）。"""
import json, os

DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "StudyNotesJP")
PATH = os.path.join(DIR, "config.json")

DEFAULTS = {
    "provider": "gemini",
    "models": {},             # AI の種類 -> モデル名（空なら既定）
    "api_keys": {},           # AI の種類 -> API キー
    "ollama_host": "http://localhost:11434",
    "output_dir": os.path.join(os.path.expanduser("~"), "Documents", "StudyNotesJP"),
    "deck_dir": "",           # 空ならノートと同じフォルダ
    "whisper_size": "small",
    "outputs": {"notes": True, "deck": True, "pdf": False},
    # 発音練習アプリとの連携（オンにすると英語のプレゼンを発音練習アプリの decks に保存する）
    "coach": {"enabled": False, "dir": "", "open_after": True, "use_weak": True},
    # 監視するフォルダ: [{"path": "...", "subject": "...", "kind": "recording" | "screenshots"}]
    "watch": [],
    "watch_on_start": True,
    "screenshot_idle_min": 5,
}


def load():
    cfg = json.loads(json.dumps(DEFAULTS))
    if os.path.exists(PATH):
        with open(PATH, encoding="utf-8") as f:
            saved = json.load(f)
        for k, v in saved.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    return cfg


def save(cfg):
    os.makedirs(DIR, exist_ok=True)
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def ai_settings(cfg):
    from .llm import PROVIDERS
    p = cfg["provider"]
    return {"provider": p, "model": cfg["models"].get(p) or PROVIDERS[p][1],
            "api_key": cfg["api_keys"].get(p, ""), "ollama_host": cfg.get("ollama_host")}
