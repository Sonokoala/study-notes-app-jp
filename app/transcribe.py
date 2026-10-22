"""faster-whisper を使い、この PC の中で音声を文字にする（mp4/m4a/wav をそのまま読む。外部には送らない）。"""
_model = None
_model_key = None


def transcribe(path, size="small", language=None, log=print):
    global _model, _model_key
    from faster_whisper import WhisperModel
    if _model_key != size:
        log(f"Whisper のモデル（{size}）を読み込み中…（初回はダウンロードします）")
        _model = WhisperModel(size, device="auto", compute_type="int8")
        _model_key = size
    segments, info = _model.transcribe(path, language=language, vad_filter=True)
    log(f"言語: {info.language}  長さ: {info.duration / 60:.0f} 分")
    lines = []
    for seg in segments:
        lines.append(seg.text.strip())
    return "\n".join(lines)
