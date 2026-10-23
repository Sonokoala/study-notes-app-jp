"""発音練習アプリ（Pronunciation Coach）との連携。

https://github.com/Sonokoala/pronunciation-coach を、このアプリとは別のフォルダに置いて使う。
連携をオンにすると、英語のプレゼンを発音練習アプリの decks フォルダに保存し、作り終えたら発音練習アプリを開く。
"""
import json, os, subprocess, sys, urllib.request, webbrowser

PORTS = range(8765, 8775)  # 発音練習アプリは 8765 から空いているポートを使う


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
