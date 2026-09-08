"""Local API launcher: load the adjacent .env without printing credentials."""
from pathlib import Path
import argparse
import os

from dotenv import load_dotenv
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Start TrialLens with local chat configuration")
    parser.add_argument("--check", action="store_true", help="Check configuration without contacting the provider")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    load_dotenv(Path(__file__).with_name(".env"), override=False)
    key_ready = bool(os.getenv("OPENAI_API_KEY", "").strip())
    model_ready = bool(os.getenv("TRIALLENS_CHAT_MODEL", "").strip())
    print("API key: " + ("configured" if key_ready else "missing — add it to apps/api/.env"))
    print("Chat model: " + ("configured" if model_ready else "missing — add it to apps/api/.env"))
    if args.check:
        return 0 if key_ready and model_ready else 1
    uvicorn.run("triallens.main:app", host="127.0.0.1", port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
