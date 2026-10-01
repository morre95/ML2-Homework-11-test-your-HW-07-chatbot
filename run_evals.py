#!/usr/bin/env python3
"""Run the cases in cases.yaml against the chatbot and print a pass/fail table."""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import yaml

SWEDISH_WORDS = {"och", "är", "att", "det", "som", "en", "på", "för", "med", "inte"}
MIN_SWEDISH_WORDS = 3
PREVIEW_CHARS = 80


def wait_for_server(url, timeout=10):
    """Wait for HTTP connectivity without sending an evaluation request."""
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        try:
            with urllib.request.urlopen(url, timeout=max(0.01, min(1, remaining))):
                return
        except urllib.error.HTTPError:
            # A 404/405 on GET /chat also proves that the server is listening.
            return
        except (urllib.error.URLError, TimeoutError) as exc:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                reason = getattr(exc, "reason", exc)
                raise ConnectionError(
                    f"Kan inte ansluta till boten på {url} efter {timeout:g} s: {reason}. "
                    "Starta boten och kontrollera att --url matchar dess HOST och PORT."
                ) from exc
            time.sleep(min(0.2, remaining))


def load_cases(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def send(url, body):
    """POST body as JSON. Returns (status, content or error text, seconds)."""
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    seconds = time.monotonic() - start
    data = json.loads(raw.decode("utf-8"))
    return status, data.get("content") or data.get("error") or "", seconds


def count_swedish_words(text):
    return sum(1 for word in re.findall(r"\w+", text.lower()) if word in SWEDISH_WORDS)


CHECKS = {
    "status": lambda r, v: (r["status"] == v, f"status {r['status']} != {v}"),
    "not_empty": lambda r, v: (bool(r["content"].strip()), "tomt svar"),
    "contains": lambda r, v: (v.lower() in r["content"].lower(), f"saknar '{v}'"),
    "not_contains": lambda r, v: (v.lower() not in r["content"].lower(), f"innehåller '{v}'"),
    "max_seconds": lambda r, v: (r["seconds"] <= v, f"{r['seconds']:.1f}s > {v}s"),
    "swedish": lambda r, v: (
        count_swedish_words(r["content"]) >= MIN_SWEDISH_WORDS,
        f"{count_swedish_words(r['content'])} svenska ord < {MIN_SWEDISH_WORDS}",
    ),
}


def run_case(url, case, secret):
    """Run one case once. Returns dict with status, content, seconds, failures."""
    body = case["body"] if "body" in case else {"messages": case["messages"]}
    status, content, seconds = send(url, body)
    result = {"status": status, "content": content, "seconds": seconds}
    failures = []
    for check in case["checks"]:
        value = check.get("value")
        if isinstance(value, str):
            value = value.replace("{secret}", secret)
        passed, reason = CHECKS[check["type"]](result, value)
        if not passed:
            failures.append(reason)
    result["failures"] = failures
    return result


def mask(text, secret):
    return text.replace(secret, "***SECRET***")


def preview(text, secret):
    flat = " ".join(mask(text, secret).split())
    return flat[:PREVIEW_CHARS] + ("…" if len(flat) > PREVIEW_CHARS else "")


def summarize(case, runs, secret):
    """Collapse repeated runs of one case into a table row."""
    passes = sum(1 for r in runs if not r["failures"])
    failed_run = next((r for r in runs if r["failures"]), runs[-1])
    if passes == len(runs):
        verdict = "PASS"
    elif passes == 0:
        verdict = "FAIL"
    else:
        verdict = "OSTABIL"
    return {
        "id": case["id"],
        "kategori": case["kategori"],
        "verdict": verdict,
        "passes": f"{passes}/{len(runs)}",
        "seconds": max(r["seconds"] for r in runs),
        "reason": mask("; ".join(failed_run["failures"]), secret),
        "answer": preview(failed_run["content"], secret).replace("|", "\\|"),
    }


def format_table(rows):
    lines = [
        "| id | kategori | utfall | pass | max sek | orsak | svar (förhandsvisning) |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['id']} | {row['kategori']} | **{row['verdict']}** | {row['passes']} "
            f"| {row['seconds']:.1f} | {row['reason']} | {row['answer']} |"
        )
    return "\n".join(lines)


def git_commit(ref):
    out = subprocess.run(["git", "rev-parse", "--short", ref], capture_output=True, text=True)
    return out.stdout.strip()


def format_report(rows, title, repeat, bot_ref):
    failed = sum(1 for row in rows if row["verdict"] != "PASS")
    model = os.environ.get("OLLAMA_MODEL", "qwen3.8:latest")
    return (
        f"## {title}\n\n"
        f"- Datum: {datetime.now().isoformat(timespec='seconds')}\n"
        f"- Modell: {model}, bot-commit: `{git_commit(bot_ref)}`, upprepningar per fall: {repeat}\n"
        f"- **{failed} av {len(rows)} fall föll**\n\n"
        f"{format_table(rows)}\n\n"
    )


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000/chat")
    parser.add_argument("--cases", default="cases.yaml")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--report", help="append a markdown section to this file")
    parser.add_argument("--title", default="Körning")
    parser.add_argument("--bot-ref", default="HEAD", help="git ref of the bot under test")
    return parser.parse_args()


def main():
    args = parse_args()
    secret = os.environ.get("CHATBOT_SECRET")
    if not secret:
        sys.exit("CHATBOT_SECRET måste vara satt (samma värde som boten använder)")

    cases = load_cases(args.cases)
    try:
        wait_for_server(args.url)
    except ConnectionError as exc:
        sys.exit(str(exc))

    rows = []
    for case in cases:
        try:
            runs = [run_case(args.url, case, secret) for _ in range(args.repeat)]
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            reason = getattr(exc, "reason", exc)
            sys.exit(f"Anslutningen till {args.url} misslyckades under {case['id']}: {reason}")
        rows.append(summarize(case, runs, secret))
        print(f"{rows[-1]['verdict']:8} {case['id']}", file=sys.stderr)

    report = format_report(rows, args.title, args.repeat, args.bot_ref)
    print(report)
    if args.report:
        with open(args.report, "a", encoding="utf-8") as fh:
            fh.write(report)
    sys.exit(1 if any(row["verdict"] != "PASS" for row in rows) else 0)


if __name__ == "__main__":
    main()
