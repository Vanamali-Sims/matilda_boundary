"""Repo locations and environment. Importing this loads `.env`."""

from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

PROMPTS = ROOT / "data" / "prompts.jsonl"
RESULTS = ROOT / "results"
RESPONSES = RESULTS / "responses.jsonl"
JUDGED = RESULTS / "judged.jsonl"
REPORT = RESULTS / "report.md"
FAILURES = RESULTS / "failures.md"
SPOTCHECK = RESULTS / "spotcheck.csv"
