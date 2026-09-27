from core import speech


def test_brev_request_sends_token(monkeypatch, tmp_path):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF")
    seen = {}

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"text": "hi", "provider": "brev-whisper"}

    def fake_post(url, files=None, data=None, headers=None, timeout=None):
        seen["headers"] = headers or {}
        return Resp()

    monkeypatch.setenv("BREV_WHISPER_URL", "https://brev.example")
    monkeypatch.setenv("WHISPER_TOKEN", "t0k")
    monkeypatch.setattr("requests.post", fake_post)
    assert speech._transcribe_brev(str(audio))["text"] == "hi"
    assert seen["headers"].get("X-Wakil-Key") == "t0k"
