"""How much does opening a new connection per request cost, from where you are?

matilda-client 0.3.0 builds a fresh httpx.AsyncClient for every call (see
MatildaClient._http, whose comment notes a persistent client as a possible later
optimisation). This script times the same small unauthenticated request against
Matilda's public config endpoint both ways:

  A) new client per request (what the SDK does today)
  B) one shared client (connection reused)

  python -m matilda_eval bench --n 30
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx

URL = "https://matilda.maincode.com/api/config/public"


async def fresh(n: int) -> list[float]:
    out = []
    for _ in range(n):
        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(URL)
        out.append((time.perf_counter() - t0) * 1000)
        _ = r.status_code
    return out


async def shared(n: int) -> list[float]:
    out = []
    async with httpx.AsyncClient(timeout=20) as c:
        await c.get(URL)  # warm-up: open the connection once
        for _ in range(n):
            t0 = time.perf_counter()
            await c.get(URL)
            out.append((time.perf_counter() - t0) * 1000)
    return out


def summary(name: str, xs: list[float]) -> float:
    med = statistics.median(xs)
    p95 = statistics.quantiles(xs, n=20)[18]
    print(f"{name:28} median {med:6.0f} ms   p95 {p95:6.0f} ms")
    return med


async def run_bench(n: int) -> None:
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(URL)
        print(f"GET {URL} -> HTTP {r.status_code}\n")
    a = summary("A) new client per request", await fresh(n))
    b = summary("B) shared client", await shared(n))
    print(f"\nOverhead per request from reconnecting: ~{a - b:.0f} ms (median), {a / b:.1f}x")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    asyncio.run(run_bench(ap.parse_args().n))


if __name__ == "__main__":
    main()
