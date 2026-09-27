"""FastAPI POST /transcribe with faster-whisper large-v3 (language="en").  Owner: D2.  Runs on Brev GPU."""
from fastapi import FastAPI, UploadFile

app = FastAPI()


@app.post("/transcribe")
async def transcribe(file: UploadFile):
    # STUB
    return {"text": "stub transcript", "provider": "brev"}
