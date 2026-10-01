#!/usr/bin/env python3
"""Minimal chatbot that proxies chat requests to a host Ollama instance."""

import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.8:latest")
INDEX_PATH = Path(__file__).with_name("index.html")
SECRET = os.environ["CHATBOT_SECRET"]
PROMPTS = Environment(loader=FileSystemLoader(Path(__file__).with_name("prompts")))
SYSTEM_PROMPT = PROMPTS.get_template("system.j2").render(secret=SECRET)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = INDEX_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self):
        if self.path != "/chat":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
            messages = payload["messages"]
        except (json.JSONDecodeError, KeyError, UnicodeDecodeError):
            self._json(400, {"error": "Expected JSON with a messages array"})
            return

        request_body = json.dumps(
            {
                "model": MODEL,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                "stream": False,
                "think": False,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat",
            data=request_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            self._json(502, {"error": f"Ollama HTTP {exc.code}: {detail}"})
            return
        except urllib.error.URLError as exc:
            self._json(502, {"error": f"Cannot reach Ollama at {OLLAMA_URL}: {exc.reason}"})
            return

        content = (data.get("message") or {}).get("content", "")
        self._json(200, {"content": content})

    def _json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}")


if __name__ == "__main__":
    print(f"Chatbot listening on {HOST}:{PORT} -> {OLLAMA_URL} ({MODEL})")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
