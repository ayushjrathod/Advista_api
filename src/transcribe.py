import os
from groq import Groq
from dotenv import load_dotenv
import asyncio
from concurrent.futures import ThreadPoolExecutor

class Transcriber:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('GROQ_API_KEY')
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")
        self.client = Groq(api_key=self.api_key)
        self._executor = ThreadPoolExecutor()

    def transcribe_sync(self, audio_path: str) -> str:
        try:
            with open(audio_path, "rb") as file:
                transcription = self.client.audio.transcriptions.create(
                    file=(audio_path, file.read()),
                    model="whisper-large-v3-turbo",
                    response_format="json",
                    language="en",
                    temperature=0.0
                )
                return transcription.text
        except Exception as e:
            print(f"Transcription error for {audio_path}: {str(e)}")
            return ""

    async def transcribe(self, audio_path: str) -> str:
        return await asyncio.get_event_loop().run_in_executor(
            self._executor, 
            self.transcribe_sync, 
            audio_path
        )

    def __del__(self):
        self._executor.shutdown(wait=False)