"""録画またはスクリーンショット -> 4分割の学習ノート（日本語）＋ 読み上げ原稿つきのプレゼン（英語）。"""
import datetime, os, re
from . import config, llm, prompts
from .builders import quad, deck
from .export import to_pdf
from .transcribe import transcribe

AUDIO_VIDEO = {".mp4", ".m4a", ".mp3", ".wav", ".mkv", ".mov", ".webm"}
IMAGES = {".png", ".jpg", ".jpeg", ".webp"}


def safe_name(s):
    return re.sub(r'[\\/:*?"<>|\r\n]+', " ", s).strip()[:60] or "ノート"


def _check_quad(spec):
    notes = spec.get("notes")
    if not isinstance(notes, list) or not notes:
        raise ValueError("AI の返事にノートのページがありませんでした")
    for i, n in enumerate(notes, 1):
        n.setdefault("num", i)
        if not (n.get("title") or n.get("title_ja")):
            n["title"] = f"トピック {i}"
        for k in ("concepts", "terms", "examples"):
            n.setdefault(k, [])
    spec["theme"] = "dark"
    return spec


def process(kind, paths, subject="", cfg=None, log=print):
    """kind: "recording"（音声・動画・.txt のファイル1つ）または "screenshots"（画像のリスト）。保存したファイルの一覧を返す。"""
    cfg = cfg or config.load()
    ai = config.ai_settings(cfg)
    if llm.PROVIDERS[ai["provider"]][2] and not ai["api_key"]:
        raise ValueError(f"{llm.PROVIDERS[ai['provider']][0]} の API キーが設定されていません（「設定」タブを確認してください）")
    today = datetime.date.today().isoformat()
    sub = safe_name(subject) if subject else "_未分類"
    out_dir = os.path.join(cfg["output_dir"], sub)
    deck_dir = os.path.join(cfg["deck_dir"], sub) if cfg.get("deck_dir") else out_dir
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(deck_dir, exist_ok=True)

    images, text = [], None
    if kind == "recording":
        path = paths[0]
        m = re.search(r"(20\d\d)[-_](\d\d)[-_](\d\d)", os.path.basename(path))
        if m:
            today = "-".join(m.groups())
        if path.lower().endswith(".txt"):
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        else:
            log(f"文字起こし中: {os.path.basename(path)}")
            text = transcribe(path, cfg.get("whisper_size", "small"), log=log)
    else:
        images = sorted(paths, key=os.path.getmtime)
        log(f"スクリーンショット {len(images)} 枚を読み込みます")
    src = prompts.source_block(kind, subject, text)

    log(f"AI に依頼中（{llm.PROVIDERS[ai['provider']][0]} / {ai['model']}）")
    t = llm.ask(ai, prompts.topic(src), images)
    base = f"{today} {safe_name(t.get('topic') or 'ノート')}"
    log(f"トピック: {base}")
    saved = []
    if kind == "recording" and not paths[0].lower().endswith(".txt"):
        p = os.path.join(out_dir, base + " - 文字起こし.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        saved.append(p)

    jobs = [("notes", " - 学習ノート.pptx", "学習ノート", prompts.quad, out_dir),
            ("deck", " - プレゼン_EN.pptx", "英語のプレゼン", prompts.deck, deck_dir)]
    for key, suffix, label, make_prompt, folder in jobs:
        if not cfg["outputs"].get(key, True):
            continue
        log(f"{label}を作成中")
        spec = llm.ask(ai, make_prompt(src), images)
        out = os.path.join(folder, base + suffix)
        if key == "notes":
            spec = _check_quad(spec)
            spec.setdefault("course", subject)
            spec.setdefault("footer", f"{subject} 学習ノート" if subject else "学習ノート")
            quad.build(spec, out)
        else:
            spec["lang"] = "en"
            deck.build(spec, out)
        saved.append(out)
        if cfg["outputs"].get("pdf", False):
            pdf = to_pdf(out, log)
            if pdf:
                saved.append(pdf)
    log("完了: " + out_dir)
    return saved
