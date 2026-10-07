"""Dialogue audio: placeholder voices from espeak-ng, or real recordings, plus
amplitude-driven mouth shapes for lip flap."""
import subprocess
import wave

import numpy as np

RATE = 22050


def _read_wav(path):
    with wave.open(str(path)) as w:
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data.astype(np.float32) / 32768.0


def synth(text, voice, out_path):
    """Speak `text` with espeak-ng into a mono RATE wav."""
    tmp = str(out_path) + ".raw.wav"
    subprocess.run(["espeak-ng", "-v", voice.get("espeak", "en-us"),
                    "-p", str(voice.get("pitch", 50)), "-s", str(voice.get("speed", 165)),
                    "-w", tmp, text], check=True)
    return load_recording(tmp, out_path)


def load_recording(src, out_path):
    """Normalize any audio file to mono RATE wav and return its samples."""
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src),
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
