import os
import random
import subprocess
import sys
import tempfile

import pyttsx3

from utils import settings

_MACOS_NOVELTY_VOICES = {
    "Albert",
    "Bad News",
    "Bahh",
    "Bells",
    "Boing",
    "Bubbles",
    "Cellos",
    "Fred",
    "Good News",
    "Jester",
    "Junior",
    "Kathy",
    "Organ",
    "Ralph",
    "Superstar",
    "Trinoids",
    "Whisper",
    "Wobble",
    "Zarvox",
}
_MACOS_PREFERRED_VOICES = [
    "Samantha",
    "Daniel",
    "Karen",
    "Rishi",
    "Tessa",
    "Moira",
    "Aman",
    "Tara",
    "Alex",
]


def _get_macos_voices() -> list[str]:
    """Returns available English local macOS `say` voices, preferring natural voices."""
    try:
        out = subprocess.check_output(["say", "-v", "?"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return []

    english_voices = []
    for line in out.splitlines():
        parts = line.split("#")[0].strip().rsplit(None, 1)
        if len(parts) != 2:
            continue
        voice_name, locale = parts
        voice_name = voice_name.strip()
        if locale.startswith("en_") and voice_name not in _MACOS_NOVELTY_VOICES:
            english_voices.append(voice_name)

    ordered = [v for v in _MACOS_PREFERRED_VOICES if v in english_voices]
    for v in english_voices:
        if v not in ordered:
            ordered.append(v)
    return ordered


class pyttsx:
    def __init__(self):
        self.max_chars = 5000
        self.voices = []
        self._macos_voices = _get_macos_voices() if sys.platform == "darwin" else []

    def run(
        self,
        text: str,
        filepath: str,
        random_voice=False,
    ):
        voice_id_raw = settings.config["settings"]["tts"].get("python_voice", "0")
        voice_num_raw = settings.config["settings"]["tts"].get("py_voice_num", "2")
        voice_id = int(voice_id_raw) if str(voice_id_raw).strip().isdigit() else 0
        voice_num = int(voice_num_raw) if str(voice_num_raw).strip().isdigit() else 2
        voice_num = max(1, voice_num)

        if sys.platform == "darwin":
            self._run_macos(text, filepath, voice_id, voice_num, random_voice)
            return

        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        if voices:
            pool_size = min(voice_num, len(voices))
            if random_voice:
                chosen_idx = random.randrange(pool_size)
            else:
                chosen_idx = voice_id % len(voices)
            engine.setProperty("voice", voices[chosen_idx].id)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
            tmp_path = tmp_audio.name
        try:
            engine.save_to_file(text, tmp_path)
            engine.runAndWait()
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    tmp_path,
                    "-codec:a",
                    "libmp3lame",
                    "-qscale:a",
                    "4",
                    "-loglevel",
                    "error",
                    filepath,
                ],
                check=True,
            )
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _run_macos(
        self,
        text: str,
        filepath: str,
        voice_id: int,
        voice_num: int,
        random_voice: bool,
    ):
        """Generates local MP3 audio on macOS using built-in `say` and `ffmpeg`."""
        chosen_voice = None
        if self._macos_voices:
            pool_size = min(voice_num, len(self._macos_voices))
            if random_voice:
                chosen_voice = random.choice(self._macos_voices[:pool_size])
            else:
                chosen_voice = self._macos_voices[voice_id % len(self._macos_voices)]

        with (
            tempfile.NamedTemporaryFile(mode="w", suffix=".txt", encoding="utf-8", delete=False) as txt_f,
            tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as aiff_f,
        ):
            txt_f.write(text)
            txt_path = txt_f.name
            aiff_path = aiff_f.name

        try:
            cmd = ["say"]
            if chosen_voice:
                cmd.extend(["-v", chosen_voice])
            cmd.extend(["-o", aiff_path, "-f", txt_path])
            subprocess.run(cmd, check=True)
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    aiff_path,
                    "-codec:a",
                    "libmp3lame",
                    "-qscale:a",
                    "4",
                    "-loglevel",
                    "error",
                    filepath,
                ],
                check=True,
            )
        finally:
            for p in (txt_path, aiff_path):
                if os.path.exists(p):
                    os.remove(p)

    def randomvoice(self):
        return random.choice(self.voices) if self.voices else 0
