"""Audio -> text.  Owner: D1.

Chain: Brev Whisper (BREV_WHISPER_URL) -> Groq Whisper large-v3 -> Gemini audio. language="en".
convert_audio(): ffmpeg .opus -> 16 kHz mono .wav. Cache transcripts by file hash in cache/.
"""


def transcribe(audio_path):
    """Return {"text": str, "provider": str}."""
    # STUB
    return {"text": "Okay, I'll send you the deposit on Friday.", "provider": "stub"}
