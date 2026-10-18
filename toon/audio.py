"""Dialogue audio: cloned voices (Chatterbox), placeholder voices from
espeak-ng, or real recordings, plus amplitude-driven mouth shapes for lip flap."""
import hashlib
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

RATE = 22050
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "out" / "voice_cache"
_clone_model = None
_warned = set()


def _read_wav(path):
    with wave.open(str(path)) as w:
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data.astype(np.float32) / 32768.0


def synth(text, voice, out_path):
    """Speak `text` in the character's voice into a mono RATE wav.

    Uses a Chatterbox clone of `voice.reference` when that file exists and
    chatterbox-tts is installed, otherwise the espeak-ng placeholder."""
    ref = voice.get("reference")
    if os.environ.get("TOON_PREVIEW"):
        return _espeak(text, voice, out_path)     # fast draft render, skip cloning
    if ref and (ROOT / ref).exists():
        try:
            return _clone(text, voice, ROOT / ref, out_path)
        except ImportError:
            _warn("chatterbox-tts is not installed, using espeak (pip install chatterbox-tts)")
    elif ref:
        _warn(f"no voice sample at {ref}, using espeak")
    return _espeak(text, voice, out_path)


def _warn(msg):
    if msg not in _warned:
        _warned.add(msg)
        print(f"voice: {msg}", file=sys.stderr)


def _clone(text, voice, ref, out_path):
    """Chatterbox zero-shot clone, cached by text, sample, and settings so
    re-rendering an episode only generates lines that changed."""
    global _clone_model
    exaggeration = float(voice.get("exaggeration", 0.5))
    cfg = float(voice.get("cfg_weight", 0.5))
    sample = hashlib.sha256(ref.read_bytes()).hexdigest()
    key = hashlib.sha256(f"{text}|{sample}|{exaggeration}|{cfg}".encode()).hexdigest()[:24]
    cached = CACHE / f"{key}.wav"
    if not cached.exists():
        import torch
        from chatterbox.tts import ChatterboxTTS
        if _clone_model is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            ckpt = os.environ.get("CHATTERBOX_CKPT")
            _clone_model = (ChatterboxTTS.from_local(ckpt, device) if ckpt
                            else ChatterboxTTS.from_pretrained(device))
        wav = _clone_model.generate(text, audio_prompt_path=str(ref),
                                    exaggeration=exaggeration, cfg_weight=cfg)
        pcm = (wav.squeeze(0).numpy().clip(-1, 1) * 32767).astype(np.int16)
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_suffix(".tmp.wav")
        with wave.open(str(tmp), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(_clone_model.sr)
            w.writeframes(pcm.tobytes())
        tmp.rename(cached)
    return load_recording(cached, out_path, float(voice.get("pitch_shift", 0)))


def _espeak(text, voice, out_path):
    tmp = str(out_path) + ".raw.wav"
    subprocess.run(["espeak-ng", "-v", voice.get("espeak", "en-us"),
                    "-p", str(voice.get("pitch", 50)), "-s", str(voice.get("speed", 165)),
                    "-w", tmp, text], check=True)
    return load_recording(tmp, out_path)


def load_recording(src, out_path, pitch_shift=0.0):
    """Normalize any audio file to mono RATE wav and return its samples.

    pitch_shift moves the pitch by that many semitones while keeping the
    voice's timbre (rubberband with preserved formants)."""
    af = ["-af", f"rubberband=pitch={2 ** (pitch_shift / 12):.5f}:formant=preserved"] \
        if pitch_shift else []
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), *af,
                    "-ac", "1", "-ar", str(RATE), "-sample_fmt", "s16", str(out_path)],
                   check=True)
    return _read_wav(out_path)


def mouth_shapes(samples, fps):
    """One mouth shape per video frame from loudness: closed, small, o or wide."""
    hop = RATE // fps
    n = int(np.ceil(len(samples) / hop))
    rms = np.array([np.sqrt(np.mean(samples[i * hop:(i + 1) * hop] ** 2) + 1e-12)
                    for i in range(n)])
    peak = rms.max() if n else 1.0
    shapes = []
    for i, level in enumerate(rms / peak):
        if level < 0.12:
            shapes.append("closed")
        elif level < 0.45:
            shapes.append("small" if i % 3 else "o")
        else:
            shapes.append("wide")
    return shapes


def write_mix(clips, total_samples, out_path):
    """clips: list of (start_sample, samples)."""
    mix = np.zeros(total_samples, dtype=np.float32)
    for start, s in clips:
        end = min(total_samples, start + len(s))
        mix[start:end] += s[:end - start]
    mix = np.clip(mix, -1, 1)
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
