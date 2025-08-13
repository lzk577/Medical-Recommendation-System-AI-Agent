# speechtext_server.py
import os, tempfile, shutil, logging
from pathlib import Path
from dotenv import load_dotenv
from openai import AsyncOpenAI
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
load_dotenv()
API_CLIENT = AsyncOpenAI()

app = FastMCP("speechtext_server")

@app.tool()
async def transcribe_audio(file_path: str, language_code: str) -> str:
    """Transcribe a local audio file with Whisper. Returns plain text."""
    suffix = Path(file_path).suffix
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = tmp.name
    tmp.close()
    try:
        shutil.copy(file_path, tmp_path)
        logging.info(f"Transcribing {file_path} -> {tmp_path} [{language_code}]")
        with open(tmp_path, "rb") as f:
            r = await API_CLIENT.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language=language_code
            )
        return r.text
    except Exception as e:
        logging.exception("Transcription failed")
        return f"[Error] {e}"
    finally:
        try:
            os.remove(tmp_path)
            logging.info(f"Cleaned up {tmp_path}")
        except Exception:
            pass

if __name__ == "__main__":
    app.run()
