"""
TTS client module using Google Cloud Text-to-Speech with SSML for natural pauses,
plus a helper to list available WaveNet voices.
"""

import os
import logging
from typing import Optional, List
from google.cloud import texttospeech
from utils import format_timestamp


class TTSClient:
    """
    Text-to-Speech client for Google Cloud WaveNet voices,
    with SSML pauses and voice‐listing support.
    """

    def __init__(
        self,
        language_code: str,
        voice_name: str,
        speaking_rate: float,
        pitch: float,
        audio_encoding: texttospeech.AudioEncoding,
    ) -> None:
        try:
            self.client = texttospeech.TextToSpeechClient()
        except Exception as e:
            logging.error("Failed to initialize TTS client: %s", e)
            raise
        self.lang = language_code
        self.voice = voice_name
        self.rate = speaking_rate
        self.pitch = pitch
        self.encoding = audio_encoding

    def synthesize(
        self,
        text: str,
        output_dir: str,
        filename: Optional[str] = None,
    ) -> str:
        """
        Synthesize the given text (with SSML breaks) and write to file.
        Returns the path to the audio file.
        """
        os.makedirs(output_dir, exist_ok=True)

        # Split into sentences and inject SSML breaks
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        ssml_parts = ["<speak>"]
        for i, s in enumerate(sentences):
            ssml_parts.append(f"<p>{s}.</p>")
            if i == 0:
                ssml_parts.append('<break time="800ms"/>')
            elif i == len(sentences) - 1:
                ssml_parts.append('<break time="600ms"/>')
            else:
                ssml_parts.append('<break time="400ms"/>')
        ssml_parts.append("</speak>")
        ssml_text = "".join(ssml_parts)

        synthesis_input = texttospeech.SynthesisInput(ssml=ssml_text)
        voice_params = texttospeech.VoiceSelectionParams(
            language_code=self.lang,
            name=self.voice,
        )
        audio_cfg = texttospeech.AudioConfig(
            audio_encoding=self.encoding,
            speaking_rate=self.rate,
            pitch=self.pitch,
        )

        try:
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_cfg,
            )
        except Exception as e:
            logging.error("TTS API request failed: %s", e)
            raise

        if not filename:
            ts = format_timestamp()
            ext = "mp3" if self.encoding == texttospeech.AudioEncoding.MP3 else "wav"
            filename = f"travel_report_{ts}.{ext}"
        out_path = os.path.join(output_dir, filename)

        try:
            with open(out_path, "wb") as f:
                f.write(response.audio_content)
            logging.info("Audio content written to %s", out_path)
        except Exception as e:
            logging.error("Failed to write audio file: %s", e)
            raise

        return out_path

    def list_voices(self, language_code: Optional[str] = None) -> List[str]:
        """
        List available WaveNet voices for the given language (defaults to self.lang).
        Returns a list of voice names.
        """
        lang = language_code or self.lang
        try:
            response = self.client.list_voices(language_code=lang)
            # Filter to WaveNet voices that support this language
            voices = [
                v.name
                for v in response.voices
                if lang in v.language_codes and "WaveNet" in v.name
            ]
            return voices
        except Exception as e:
            logging.error("Failed to list voices: %s", e)
            return []
