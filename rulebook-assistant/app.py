"""Web front end for the Rulebook Assistant. Run with: python app.py"""
import getpass
import json
import os
import re
import sys
import uuid
from pathlib import Path

import anthropic
from flask import Flask, Response, jsonify, request, send_from_directory

from assistant import Assistant
from pack import PackError, load_pack

HERE = Path(__file__).parent
REGISTER = Path(os.environ.get(
    "RULEBOOK_REGISTER", HERE.parent / "Rulebook Agent Document Register.xlsx"))
DATA_SOURCES = Path(os.environ.get("RULEBOOK_DATA_SOURCES", HERE.parent / "Data Sources"))
MAX_QUESTION_CHARS = 4000


def clean_key(raw: str) -> str:
    """Terminals can wrap a pasted key in bracketed-paste markers or add control characters."""
    return re.sub(r"[^\x21-\x7e]", "", re.sub(r"\x1b\[20[01]~", "", raw))


def friendly_error(error: Exception) -> str:
    if isinstance(error, TypeError) and "authentication" in str(error):
        return "No API key found. Set ANTHROPIC_API_KEY and restart the app."
    if isinstance(error, anthropic.AuthenticationError):
        return f"The API key was rejected ({error.message}). Check it and restart the app."
    if isinstance(error, anthropic.RateLimitError):
        return "The API rate limit was reached. Wait a moment and ask again."
    if isinstance(error, anthropic.APIStatusError):
        return f"The API returned an error ({error.status_code}): {error.message}"
    if isinstance(error, anthropic.APIConnectionError):
        return "Could not reach the API. Check your connection and ask again."
    return f"Something went wrong: {error}"


def sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def create_app(assistant: Assistant) -> Flask:
    app = Flask(__name__, static_folder=None)

    @app.get("/")
    def index():
        return send_from_directory(HERE / "static", "index.html")

    @app.get("/api/pack")
    def pack_details():
        pack = assistant.pack
        return jsonify({
            "pack_id": pack.pack_id,
            "warnings": list(pack.warnings),
            "documents": [
                {"title": d.title, "file": d.file, "revised": d.revised}
                for d in pack.documents
            ],
        })

    @app.post("/api/ask")
    def ask():
        body = request.get_json(silent=True) or {}
        question = str(body.get("question", "")).strip()
        if not question:
            return jsonify({"error": "Enter a question."}), 400
        if len(question) > MAX_QUESTION_CHARS:
            return jsonify({"error": f"Keep questions under {MAX_QUESTION_CHARS} characters."}), 400
        conversation_id = str(body.get("conversation_id") or uuid.uuid4())

        def events():
            yield sse({"type": "conversation", "id": conversation_id})
            try:
                for event in assistant.ask(conversation_id, question):
                    yield sse(event)
            except (anthropic.APIError, TypeError) as error:
                # The SDK raises TypeError when it finds no credentials at all
                yield sse({"type": "error", "message": friendly_error(error)})

        return Response(events(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache"})

    return app


if __name__ == "__main__":
    try:
        pack = load_pack(REGISTER, DATA_SOURCES)
    except PackError as error:
        sys.exit(str(error))
    print(f"Loaded pack {pack.pack_id}: " + ", ".join(d.title for d in pack.documents))
    for warning in pack.warnings:
        print(f"Warning: {warning}")
    if not os.environ.get("ANTHROPIC_API_KEY") and sys.stdin.isatty():
        key = clean_key(getpass.getpass("Paste your Claude API key and press Enter (it stays hidden): "))
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key
            print(f"Key received: {key[:10]}..., {len(key)} characters")
    create_app(Assistant(pack)).run(host="127.0.0.1", port=5000, threaded=True)
