"""発音練習アプリ（Pronunciation Coach）との連携。

https://github.com/Sonokoala/pronunciation-coach を、このアプリとは別のフォルダに置いて使う。
連携をオンにすると、英語のプレゼンを発音練習アプリの decks フォルダに保存し、作り終えたら発音練習アプリを開く。
"""
import json, os, subprocess, sys, urllib.request, webbrowser

PORTS = range(8765, 8775)  # 発音練習アプリは 8765 から空いているポートを使う
# 苦手な単語の集計で数えない、短い機能語
FILLER = {"a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "at", "for", "by", "with", "from",
          "is", "are", "was", "it", "its", "it's", "this", "that", "i", "you", "we", "they", "be", "as"}


def check(coach_dir):
    """発音練習アプリのフォルダとして使えなければ理由を返す（使えれば空文字）。"""
    if not coach_dir:
        return "発音練習アプリのフォルダが指定されていません"
    if not os.path.isfile(os.path.join(coach_dir, "server.py")):
        return f"発音練習アプリが見つかりません（server.py がありません）: {coach_dir}"
    return ""


def decks_dir(coach_dir):
    return os.path.join(coach_dir, "decks")


def _running(decks):
    """decks フォルダを開いている発音練習アプリの URL（なければ None）。"""
    want = os.path.basename(os.path.normpath(decks))
    for port in PORTS:
        url = f"http://localhost:{port}/"
        try:
            with urllib.request.urlopen(url + "api/sentences", timeout=1.5) as r:
                data = json.load(r)
        except Exception:
            continue
        if "decks" in data and data.get("deck") == want:
            return url
    return None


def open_coach(coach_dir, log=print):
    """発音練習アプリを開く。decks フォルダで起動済みならページを開くだけ、なければ新しく起動する。"""
    reason = check(coach_dir)
    if reason:
        log(reason)
        return
    decks = decks_dir(coach_dir)
    url = _running(decks)
    if url:
        log(f"発音練習アプリを開きます: {url}")
        webbrowser.open(url)
        return
    log("発音練習アプリを起動します（終了するときは、黒いウィンドウを閉じます）")
    # 発音練習アプリは Python の標準ライブラリだけで動くので、このアプリの Python で起動できる
    subprocess.Popen([sys.executable, "server.py", decks], cwd=coach_dir,
                     creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))


def weak_points(coach_dir, days=30, top_sounds=5, top_words=10):
    """発音練習アプリの練習ログ（notes/練習ログ.csv）から、最近の苦手な音と単語を集計する。

    戻り値: {"sounds": [("ɹ", "l", 52, 7), ...], "words": ["supports", ...]}
    sounds は (音, よく聞き間違えられた音 or "", 平均点, 回数) で、2回以上出た音を点の低い順に並べる。
    ログがなければ空の結果を返す。
    """
    import csv, datetime, re
    from collections import Counter, defaultdict
    log = os.path.join(coach_dir, "notes", "練習ログ.csv")
    if not os.path.isfile(log):
        return {"sounds": [], "words": []}
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    scores, heard, words = defaultdict(list), defaultdict(Counter), Counter()
    with open(log, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if (row.get("date") or "") < since:
                continue
            for ipa, alt, score in re.findall(r"/([^/]+)/(?:→/([^/]+)/)?\((\d+)\)", row.get("low_sounds") or ""):
                scores[ipa].append(int(score))
                if alt:
                    heard[ipa][alt] += 1
            for word in re.findall(r"([A-Za-z][A-Za-z'\-]*)\(\d+\)", row.get("low_words") or ""):
                if word.lower() not in FILLER:
                    words[word.lower()] += 1
    sounds = [(ipa, heard[ipa].most_common(1)[0][0] if heard[ipa] else "", round(sum(s) / len(s)), len(s))
              for ipa, s in scores.items() if len(s) >= 2]
    sounds.sort(key=lambda x: x[2])
    return {"sounds": sounds[:top_sounds], "words": [w for w, _ in words.most_common(top_words)]}
