#!/usr/bin/env python3
"""Minimal HTTP load smoke test (stdlib only).

Fires `--requests` GET requests at `--url` using a pool of threads and
reports throughput, failure count, and the p50/p95 latency.

Usage:
    python scripts/load_smoke.py --url http://localhost:5000/health --requests 500 --workers 25

ponytail: single endpoint at a time; add headers (auth) or more paths only
when real load modeling is needed.
"""
import argparse
import ssl
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor


def _hit(url):
    ctx = ssl._create_unverified_context() if url.startswith("https") else None
    start = time.perf_counter()
    with urllib.request.urlopen(url, timeout=15, context=ctx) as resp:
        status = resp.status
    return status, time.perf_counter() - start


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:5000/health")
    ap.add_argument("--requests", type=int, default=250, help="total requests")
    ap.add_argument("--workers", type=int, default=25, help="pool size")
    args = ap.parse_args()

    start = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(_hit, args.url) for _ in range(args.requests)]
        for f in futures:
            try:
                results.append(f.result())
            except Exception as exc:
                results.append((0, 0.0))
    elapsed = time.perf_counter() - start

    statuses = [s for s, _ in results]
    failures = statuses.count(0)
    non200 = sum(1 for s in statuses if s and s >= 400)
    lats = sorted(t for _, t in results if t)

    def p(percent):
        if not lats:
            return 0.0
        return lats[min(len(lats) - 1, int(percent / 100 * len(lats)))]

    print(f"url={args.url} requests={args.requests} workers={args.workers}")
    print(f"duration={elapsed:.2f}s throughput={args.requests / elapsed:.1f} req/s")
    print(f"failures={failures} non-2xx={non200}")
    print(f"latency p50={p(50) * 1000:.0f}ms p95={p(95) * 1000:.0f}ms")
    if failures or non200:
        raise SystemExit(1)


if __name__ == "__main__":
    main()