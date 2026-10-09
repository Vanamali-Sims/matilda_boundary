"""Send every prompt in data/prompts.jsonl to each target and save the raw responses.

Targets:
  matilda_chat  hosted Matilda chat, called through Maincode's own Python SDK
                (matilda-client). Logs in once with a device code.
  kimi_k3       base Kimi K3 through OpenRouter (OPENROUTER_API_KEY in .env).
  matilda_code  optional: the Matilda Code endpoint, model matilda-code-1.0
                (MATILDA_API_KEY in .env).

Usage:
  python -m matilda_eval run --targets matilda_chat kimi_k3
  python -m matilda_eval run --targets kimi_k3 --limit 5

Re-running is safe: prompt/target pairs that already have a response are skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time
from datetime import datetime, timezone

import httpx

from matilda_eval.io import append_jsonl, read_jsonl
from matilda_eval.paths import PROMPTS, RESPONSES

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MATILDA_CODE_URL = "https://matilda.maincode.com/api/v1/code/chat/completions"


def load_prompts(limit: int | None) -> list[dict]:
    rows = read_jsonl(PROMPTS)
    return rows[:limit] if limit else rows


def done_keys() -> set[tuple[str, str]]:
    return {(r["id"], r["target"]) for r in read_jsonl(RESPONSES) if not r.get("error")}


def append(record: dict) -> None:
    append_jsonl(RESPONSES, record)


# --- targets -----------------------------------------------------------------


async def call_openai_compatible(http: httpx.AsyncClient, url: str, key: str, model: str, prompt: str) -> dict:
    resp = await http.post(
        url,
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 4000},
        timeout=300,
    )
    resp.raise_for_status()
    data = resp.json()
    msg = data["choices"][0]["message"]
    return {
        "response": msg.get("content") or "",
        "model_reported": data.get("model"),
        "provider": data.get("provider"),
        "finish_reason": data["choices"][0].get("finish_reason"),
    }


class MatildaChat:
    """Wraps the official SDK. A fresh conversation is used for every prompt so
    that answers can't influence each other."""

    def __init__(self) -> None:
        from matilda_client import MatildaClient  # imported lazily so kimi-only runs work without it

        self.client = MatildaClient(base_url=os.getenv("MATILDA_BASE_URL", "https://matilda.maincode.com/api"))

    async def login(self) -> None:
        print("Logging in to Matilda: open the URL below and enter the code.")
        await self.client.auth.login_with_device_flow(client_id=os.getenv("MATILDA_CLIENT_ID", "matilda-code"))

    async def ask(self, prompt: str) -> dict:
        r = await self.client.chat.create(input=prompt)
        replaced = [e for e in r.events if type(e).__name__ == "OutputTextReplace"]
        return {
            "response": r.output_text,
            "model_reported": None,
            "safety_replaced": bool(replaced),
            "safety_categories": sorted({c for e in replaced for c in (getattr(e, "categories", None) or [])}),
            "stream_errors": [f"{e.code}: {e.message}" for e in r.errors],
            "truncated_reason": r.truncated_reason,
            "output_tokens": r.usage.output_tokens if r.usage else None,
        }


# --- runner --------------------------------------------------------------------


async def run(targets: list[str], limit: int | None, concurrency: int) -> None:
    prompts = load_prompts(limit)
    skip = done_keys()
    sem = asyncio.Semaphore(concurrency)
    stop = {t: False for t in targets}

    matilda = None
    if "matilda_chat" in targets:
        matilda = MatildaChat()
        await matilda.login()

    async with httpx.AsyncClient() as http:

        async def one(p: dict, target: str) -> None:
            if (p["id"], target) in skip or stop[target]:
                return
            async with sem:
                if stop[target]:
                    return
                rec = {"id": p["id"], "category": p["category"], "target": target, "prompt": p["prompt"]}
                t0 = time.perf_counter()
                for attempt in range(3):
                    try:
                        if target == "kimi_k3":
                            out = await call_openai_compatible(
                                http, OPENROUTER_URL, os.environ["OPENROUTER_API_KEY"],
                                os.getenv("KIMI_MODEL", "moonshotai/kimi-k3"), p["prompt"],
                            )
                        elif target == "matilda_code":
                            out = await call_openai_compatible(
                                http, MATILDA_CODE_URL, os.environ["MATILDA_API_KEY"],
                                os.getenv("MATILDA_CODE_MODEL", "matilda-code-1.0"), p["prompt"],
                            )
                        else:
                            out = await matilda.ask(p["prompt"])
                        rec.update(out)
                        rec["error"] = None
                        break
                    except Exception as err:  # keep going; the error is recorded
                        name = type(err).__name__
                        rec["error"] = f"{name}: {err}"
                        if name == "QuotaExceededError":
                            print(f"[{target}] daily quota hit (resets {getattr(err, 'resets_at', '?')}). Stopping this target.")
                            stop[target] = True
                            break
                        await asyncio.sleep(2 ** attempt * 3)
                rec["latency_s"] = round(time.perf_counter() - t0, 2)
                rec["ts"] = datetime.now(timezone.utc).isoformat()
                append(rec)
                status = "ERR " + rec["error"][:80] if rec["error"] else "ok"
                print(f"{target:13} {p['id']}  {rec['latency_s']:>6}s  {status}")

        await asyncio.gather(*(one(p, t) for p in prompts for t in targets))

    print(f"\nSaved to {RESPONSES}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", nargs="+", default=["matilda_chat", "kimi_k3"],
                    choices=["matilda_chat", "kimi_k3", "matilda_code"])
    ap.add_argument("--limit", type=int, default=None, help="only the first N prompts (smoke test)")
    ap.add_argument("--concurrency", type=int, default=3)
    args = ap.parse_args()
    asyncio.run(run(args.targets, args.limit, args.concurrency))


if __name__ == "__main__":
    main()
