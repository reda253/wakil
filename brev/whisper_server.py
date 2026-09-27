"""FastAPI POST /transcribe with faster-whisper large-v3 (language="en"). Runs on Brev GPU."""
import os
import shutil
import tempfile
import logging
from fastapi import FastAPI, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("whisper_server")

app = FastAPI(title="Wakil Whisper GPU Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("Initializing faster-whisper large-v3 on CUDA with float16...")
# large-v3 with float16 requires ~3.1 GB VRAM, fitting easily within 16 GB VRAM on T4
model = WhisperModel("large-v3", device="cuda", compute_type="float16")
logger.info("Whisper model loaded and ready!")


@app.get("/health")
def health():
    return {"status": "ok", "gpu": True, "model": "faster-whisper-large-v3"}


@app.post("/transcribe")
async def transcribe(file: UploadFile, language: str = Form("en")):
    logger.info(f"Received audio file for transcription: {file.filename}")
    
    # Save uploaded file to temp file
    suffix = os.path.splitext(file.filename or "")[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        # Transcribe with beam size 5 for high accuracy
        segments, info = model.transcribe(
            tmp_path,
            language=language or "en",
            beam_size=5,
            vad_filter=True, # Voice activity detection filters out silence
        )
        text = " ".join(seg.text.strip() for seg in segments)
        logger.info(f"Transcription complete: {len(text)} characters.")
        return {"text": text.strip(), "provider": "brev-whisper"}
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return {"text": "", "error": str(e), "provider": "brev-whisper"}
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
