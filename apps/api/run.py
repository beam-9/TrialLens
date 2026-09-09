"""Local API launcher: load the adjacent .env without printing credentials."""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import time

import httpx

from dotenv import load_dotenv
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Start TrialLens with local chat configuration")
    parser.add_argument("--check", action="store_true", help="Check configuration without contacting the provider")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    load_dotenv(Path(__file__).with_name(".env"), override=False)
    from triallens.conversation import chat_provider, chat_model, chat_configured
    print("Chat provider: " + chat_provider())
    print("Chat model: " + chat_model())
    print("Configuration: " + ("ready" if chat_configured() else "incomplete — check apps/api/.env"))
    if chat_provider() == "ollama":
        print("Local generation uses no API credits. The launcher starts Ollama if needed.")
    if args.check:
        return 0 if chat_configured() else 1
    ollama_process = None
    log = None
    try:
        if chat_provider() == "ollama":
            try:
                httpx.get("http://127.0.0.1:11434/api/version", timeout=2, trust_env=False).raise_for_status()
            except httpx.HTTPError:
                executable = shutil.which("ollama")
                if not executable:
                    print("Ollama is not installed. Install it, then run: ollama pull " + chat_model())
                    return 1
                log_path = Path(__file__).parent / "data" / "ollama.log"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log = log_path.open("a")
                ollama_process = subprocess.Popen([executable, "serve"], stdout=log, stderr=log,
                    env={**os.environ, "OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_NO_CLOUD": "1",
                         "OLLAMA_NUM_PARALLEL": "1", "OLLAMA_FLASH_ATTENTION": "1", "OLLAMA_KV_CACHE_TYPE": "q8_0"})
                for _ in range(30):
                    try:
                        httpx.get("http://127.0.0.1:11434/api/version", timeout=1, trust_env=False).raise_for_status()
                        break
                    except httpx.HTTPError:
                        if ollama_process.poll() is not None:
                            raise RuntimeError("Ollama stopped during startup. Check apps/api/data/ollama.log")
                        time.sleep(0.2)
                else:
                    raise RuntimeError("Ollama did not become ready. Check apps/api/data/ollama.log")
        uvicorn.run("triallens.main:app", host="127.0.0.1", port=args.port)
    finally:
        if ollama_process is not None:
            ollama_process.terminate()
            try:
                ollama_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                ollama_process.kill()
                ollama_process.wait()
        if log:
            log.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
