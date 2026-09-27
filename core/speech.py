"""Audio -> text. Owner: D1.

Chain: Brev Whisper (BREV_WHISPER_URL) -> Groq Whisper large-v3 -> Gemini audio. language="en".
convert_audio(): ffmpeg .opus -> 16 kHz mono .wav. Cache transcripts by file hash in cache/.
"""
import os
import json
import hashlib
import logging
import subprocess
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("wakil.speech")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def _get_ffmpeg_cmd() -> str:
    """Return path to ffmpeg binary (from PATH or imageio_ffmpeg)."""
    # 1. Check system PATH
    try:
        res = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass

    # 2. Check imageio_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    return "ffmpeg"


def get_file_hash(file_path: str) -> str:
    """Calculate MD5 hash of an audio file for caching."""
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def convert_audio(input_path: str, output_path: Optional[str] = None) -> str:
    """Convert any audio file (.opus, .m4a, .ogg) to 16 kHz mono .wav using ffmpeg."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Audio file not found: {input_path}")

    # If already a .wav, return as-is
    if input_path.lower().endswith(".wav"):
        return input_path

    if not output_path:
        base, _ = os.path.splitext(input_path)
        output_path = f"{base}_converted.wav"

    ffmpeg_bin = _get_ffmpeg_cmd()
    cmd = [
        ffmpeg_bin,
        "-y",               # Overwrite output
        "-i", input_path,   # Input file
        "-ar", "16000",     # 16 kHz sampling rate
        "-ac", "1",         # Mono channel
        "-c:a", "pcm_s16le",# Standard WAV PCM 16-bit
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"FFmpeg conversion failed: {result.stderr}")
        raise RuntimeError(f"FFmpeg conversion failed for {input_path}")

    return output_path


def _transcribe_brev(audio_path: str, timeout: float = 30.0) -> Dict[str, str]:
    """Transcribe using Brev faster-whisper GPU service."""
    brev_url = os.getenv("BREV_WHISPER_URL", "").strip()
    if not brev_url:
        raise ValueError("BREV_WHISPER_URL not set")

    import requests
    endpoint = brev_url if brev_url.endswith("/transcribe") else f"{brev_url.rstrip('/')}/transcribe"
    
    with open(audio_path, "rb") as f:
        files = {"file": (os.path.basename(audio_path), f)}
        data = {"language": "en"}
        headers = {"X-Wakil-Key": os.getenv("WHISPER_TOKEN", "")}
        resp = requests.post(endpoint, files=files, data=data, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        text = data.get("text", "")
        provider = data.get("provider", "brev-whisper")
        return {"text": text.strip(), "provider": provider}


def _transcribe_groq(audio_path: str, timeout: float = 25.0) -> Dict[str, str]:
    """Transcribe using Groq Whisper large-v3 in English."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY not set")

    from groq import Groq
    client = Groq(api_key=api_key, timeout=timeout)

    with open(audio_path, "rb") as f:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), f),
            model="whisper-large-v3",
            language="en",
            response_format="verbose_json",
        )
    text = transcription.text if hasattr(transcription, "text") else str(transcription)
    return {"text": text.strip(), "provider": "groq-whisper"}


def _transcribe_gemini(audio_path: str, timeout: float = 30.0) -> Dict[str, str]:
    """Transcribe using Gemini audio multimodal processing."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    from google import genai

    client = genai.Client(api_key=api_key)
    # Upload audio file to Gemini
    uploaded_file = client.files.upload(file=audio_path)
    
    prompt = (
        "Please transcribe the following audio accurately into English text. "
        "Do not include any commentary, timestamps, or formatting, only the plain English transcription."
    )
    
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    response = client.models.generate_content(
        model=model_name,
        contents=[uploaded_file, prompt],
    )
    text = response.text or ""
    return {"text": text.strip(), "provider": "gemini-audio"}


def transcribe(audio_path: str) -> Dict[str, str]:
    """Transcribe audio with fallback chain: Brev Whisper -> Groq Whisper -> Gemini Audio.
    
    Always forces language="en".
    Caches transcripts by audio file hash in cache/.
    Returns {"text": str, "provider": str}.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # 1. Check cache
    file_hash = get_file_hash(audio_path)
    cache_path = os.path.join(CACHE_DIR, f"{file_hash}.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
                logger.info(f"Loaded cached transcript for {os.path.basename(audio_path)} (provider: {cached.get('provider')})")
                return {"text": cached.get("text", ""), "provider": f"cache({cached.get('provider')})"}
        except Exception as e:
            logger.warning(f"Failed to read cache file {cache_path}: {e}")

    # 2. Convert audio if needed (.opus, .m4a -> .wav)
    converted_path = None
    transcribe_target = audio_path
    if not audio_path.lower().endswith(".wav"):
        try:
            converted_path = convert_audio(audio_path)
            transcribe_target = converted_path
        except Exception as e:
            logger.warning(f"Audio conversion failed ({e}), attempting original file directly.")

    errors = []
    result = None

    # 3. Brev Whisper (NVIDIA GPU - Highest priority)
    if os.getenv("BREV_WHISPER_URL", "").strip():
        try:
            logger.info("Attempting transcription via Brev Whisper GPU...")
            result = _transcribe_brev(transcribe_target)
            logger.info(f"Brev Whisper succeeded: {len(result['text'])} chars")
        except Exception as e:
            logger.warning(f"Brev Whisper failed: {e}. Falling back to next provider.")
            errors.append(f"brev: {e}")

    # 4. Groq Whisper large-v3
    if not result and os.getenv("GROQ_API_KEY", "").strip():
        try:
            logger.info("Attempting transcription via Groq Whisper...")
            result = _transcribe_groq(transcribe_target)
            logger.info(f"Groq Whisper succeeded: {len(result['text'])} chars")
        except Exception as e:
            logger.warning(f"Groq Whisper failed: {e}. Falling back to Gemini.")
            errors.append(f"groq: {e}")

    # 5. Gemini Audio
    if not result and os.getenv("GEMINI_API_KEY", "").strip():
        try:
            logger.info("Attempting transcription via Gemini Audio...")
            result = _transcribe_gemini(transcribe_target)
            logger.info(f"Gemini Audio succeeded: {len(result['text'])} chars")
        except Exception as e:
            logger.warning(f"Gemini Audio failed: {e}.")
            errors.append(f"gemini: {e}")

    # Clean up converted temporary wav if created in temp location
    if converted_path and converted_path != audio_path and os.path.exists(converted_path):
        try:
            os.remove(converted_path)
        except Exception:
            pass

    if not result:
        err_msg = f"All speech transcription providers failed. Errors: {'; '.join(errors)}"
        logger.error(err_msg)
        raise RuntimeError(err_msg)

    # 6. Save to cache
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to write cache file {cache_path}: {e}")

    return result
