"""4種類の AI を1つの関数で使う: ask(cfg, prompt, images) -> AI が返した JSON を dict にしたもの。"""
import base64, json, mimetypes, re
import requests

PROVIDERS = {
    # 名前: (表示名, 既定のモデル, API キーが必要か)
    "gemini": ("Gemini (Google)", "gemini-3.5-flash-lite", True),
    "claude": ("Claude (Anthropic)", "claude-sonnet-5-5", True),
    "openai": ("ChatGPT (OpenAI)", "gpt-4.1-mini", True),
    "ollama": ("Ollama（この PC で動かす）", "gemma3:12b", False),
}
# 選べるモデル（Gemini は無料枠で使えるもの）
MODEL_CHOICES = {
    "gemini": ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.1-flash-lite"],
}
TIMEOUT = 600


def _b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _mime(path):
    return mimetypes.guess_type(path)[0] or "image/png"


def _gemini(cfg, prompt, images):
    parts = [{"inline_data": {"mime_type": _mime(p), "data": _b64(p)}} for p in images]
    parts.append({"text": prompt})
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['model']}:generateContent"
    r = requests.post(url, headers={"x-goog-api-key": cfg["api_key"]}, timeout=TIMEOUT, json={
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.4},
    })
    r.raise_for_status()
    return "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"])


def _claude(cfg, prompt, images):
    content = [{"type": "image", "source": {"type": "base64", "media_type": _mime(p), "data": _b64(p)}}
               for p in images]
    content.append({"type": "text", "text": prompt})
    r = requests.post("https://api.anthropic.com/v1/messages", timeout=TIMEOUT, headers={
        "x-api-key": cfg["api_key"], "anthropic-version": "2023-06-01", "content-type": "application/json",
    }, json={"model": cfg["model"], "max_tokens": 16000, "messages": [{"role": "user", "content": content}]})
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json()["content"] if b["type"] == "text")


def _openai(cfg, prompt, images):
    content = [{"type": "image_url", "image_url": {"url": f"data:{_mime(p)};base64,{_b64(p)}"}} for p in images]
    content.append({"type": "text", "text": prompt})
    r = requests.post("https://api.openai.com/v1/chat/completions", timeout=TIMEOUT,
                      headers={"Authorization": f"Bearer {cfg['api_key']}"}, json={
        "model": cfg["model"], "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": content}],
    })
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _ollama(cfg, prompt, images):
    host = cfg.get("ollama_host") or "http://localhost:11434"
    msg = {"role": "user", "content": prompt}
    if images:
        msg["images"] = [_b64(p) for p in images]
    r = requests.post(f"{host}/api/chat", timeout=TIMEOUT * 3, json={
        "model": cfg["model"], "messages": [msg], "stream": False, "format": "json",
        "options": {"num_ctx": 32768, "temperature": 0.4},
    })
    r.raise_for_status()
    return r.json()["message"]["content"]


CALL = {"gemini": _gemini, "claude": _claude, "openai": _openai, "ollama": _ollama}


def parse_json(text):
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def ask(cfg, prompt, images=(), retries=1):
    """cfg: {"provider", "model", "api_key", "ollama_host"} （AI の種類・モデル・API キー・Ollama のアドレス）"""
    last = None
    for _ in range(retries + 1):
        text = CALL[cfg["provider"]](cfg, prompt, list(images))
        try:
            return parse_json(text)
        except (ValueError, json.JSONDecodeError) as e:
            last = e
            prompt += "\n\n前の答えは正しい JSON ではありませんでした。JSON オブジェクトだけを出力してください。"
    raise ValueError(f"AI の答えを JSON として読めませんでした: {last}")


def ollama_models(host="http://localhost:11434"):
    try:
        return [m["name"] for m in requests.get(f"{host}/api/tags", timeout=3).json()["models"]]
    except Exception:
        return []
