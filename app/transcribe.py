"""faster-whisper を使い、この PC の中で音声を文字にする（mp4/m4a/wav をそのまま読む。外部には送らない）。"""
_model = None
_model_key = None


def _load_audio(path):
    """音声・動画ファイルを 16kHz モノラルの float32 配列にする。
    faster-whisper の読み込み関数は新しい PyAV（15 以降）で失敗するので、PyAV で直接読む。"""
    import av
    import numpy as np
    chunks = []
    with av.open(path) as container:
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        for frame in container.decode(audio=0):
            chunks.extend(f.to_ndarray() for f in resampler.resample(frame))
        chunks.extend(f.to_ndarray() for f in resampler.resample(None))
    if not chunks:
        raise ValueError("音声が見つかりませんでした")
    return np.concatenate(chunks, axis=1).reshape(-1).astype(np.float32) / 32768.0


def transcribe(path, size="small", language=None, log=print):
    global _model, _model_key
    from faster_whisper import WhisperModel
    if _model_key != size:
        log(f"Whisper のモデル（{size}）を読み込み中…（初回はダウンロードします）")
        _model = WhisperModel(size, device="auto", compute_type="int8")
        _model_key = size
    segments, info = _model.transcribe(_load_audio(path), language=language, vad_filter=True)
    log(f"言語: {info.language}  長さ: {info.duration / 60:.0f} 分")
    lines = []
    for seg in segments:
        lines.append(seg.text.strip())
    return "\n".join(lines)
