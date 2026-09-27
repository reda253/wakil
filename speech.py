"""Audio -> text.  Owner: P1.

Chain: Groq Whisper large-v3 -> Gemini audio (fallback).
Convert .opus with ffmpeg if an API rejects it. Cache every transcript by filename
(never transcribe twice). Delete audio after transcription (data minimization).
"""


def convert_audio(path):
    """ffmpeg .opus -> .mp3/.wav. Return new path."""
    raise NotImplementedError


def transcribe_groq(path):
    raise NotImplementedError


def transcribe_gemini(path):
    raise NotImplementedError


def transcribe(audio_path):
    """Return {"text": str, "language": str, "provider": "groq"|"gemini"|"cache"|"stub"}."""
    # STUB: replace with cache -> groq -> gemini chain
    return {"text": "Wakha, ghadi nsiftlik l'avance nhar l'jem3a.", "language": "ar", "provider": "stub"}
