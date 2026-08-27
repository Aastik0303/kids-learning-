# -*- coding: utf-8 -*-
"""A quick end-to-end check that does not need a Groq key.

Run it from the project root:  .venv\\Scripts\\python.exe smoke_test.py

It exercises everything that does not cost money: the page is served, /health
answers, bad input is rejected, a missing key produces a readable message, and
Edge TTS actually returns playable audio.
"""

import asyncio
import sys

from fastapi.testclient import TestClient

from backend import ai, tts
from backend.main import app


def check(label: str, ok: bool, note: str = "") -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" - {note}" if note else ""))
    return ok


def main() -> int:
    results = []

    with TestClient(app) as client:
        # --- the page ------------------------------------------------------
        page = client.get("/")
        results.append(
            check(
                "GET / serves the frontend",
                page.status_code == 200 and "AI Voice Assistant" in page.text,
                f"status {page.status_code}",
            )
        )

        for asset in ("/style.css", "/app.js"):
            got = client.get(asset)
            results.append(
                check(f"GET {asset}", got.status_code == 200, f"status {got.status_code}")
            )

        # --- health --------------------------------------------------------
        health = client.get("/health")
        body = health.json()
        results.append(
            check(
                "GET /health",
                health.status_code == 200 and body["status"] == "ok",
                str(body),
            )
        )

        # --- invalid input is refused before any work happens ---------------
        empty = client.post("/chat", json={"message": ""})
        results.append(
            check("POST /chat rejects an empty message", empty.status_code == 422)
        )

        missing = client.post("/chat", json={})
        results.append(
            check("POST /chat rejects a missing message", missing.status_code == 422)
        )

        # --- a missing key is a readable sentence, not a stack trace --------
        if not ai.has_api_key():
            no_key = client.post("/chat", json={"message": "hello"})
            detail = no_key.json().get("detail", "")
            results.append(
                check(
                    "POST /chat explains a missing GROQ_API_KEY",
                    no_key.status_code == 502 and "GROQ_API_KEY" in detail,
                    detail,
                )
            )
        else:
            live = client.post("/chat", json={"message": "Say hello in one short sentence."})
            results.append(
                check(
                    "POST /chat answers with a real key",
                    live.status_code == 200 and bool(live.json().get("response")),
                    str(live.json())[:120],
                )
            )

        # --- speech --------------------------------------------------------
        spoken = client.post("/tts", json={"text": "Hello, this is a test of the voice."})
        # Either an ID3 tag, or a raw MPEG frame: 0xFF followed by three set sync
        # bits. Edge sends the raw frames, so both shapes have to count.
        head = spoken.content[:3]
        is_mp3 = spoken.status_code == 200 and (
            head == b"ID3" or (len(head) >= 2 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0)
        )
        results.append(
            check(
                "POST /tts returns playable MP3",
                is_mp3,
                f"status {spoken.status_code}, {len(spoken.content)} bytes, "
                f"type {spoken.headers.get('content-type')}",
            )
        )

        results.append(
            check("POST /tts rejects empty text", client.post("/tts", json={"text": ""}).status_code == 422)
        )

        # --- the STT seam --------------------------------------------------
        stt_reply = client.post("/stt", files={"file": ("clip.webm", b"not audio", "audio/webm")})
        results.append(
            check(
                "POST /stt explains the browser engine",
                stt_reply.status_code == 501 and "STT_ENGINE" in stt_reply.json()["detail"],
                stt_reply.json().get("detail", "")[:80],
            )
        )

    # --- the speech cleaner, on its own -------------------------------------
    dirty = "**Hi** there \U0001f60a\n\n- one\n- two\n`code`"
    cleaned = ai._clean_for_speech(dirty)
    results.append(
        check(
            "markdown and emoji are stripped before speaking",
            "*" not in cleaned and "`" not in cleaned and "\U0001f60a" not in cleaned,
            repr(cleaned),
        )
    )

    # --- text_to_speech directly --------------------------------------------
    audio = asyncio.run(tts.text_to_speech("Testing the voice function directly."))
    results.append(
        check("text_to_speech() returns audio", len(audio) > 1000, f"{len(audio)} bytes")
    )

    print()
    passed = sum(1 for ok in results if ok)
    print(f"{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
