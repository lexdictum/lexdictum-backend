#!/usr/bin/env python3
"""Simple concurrent load test for health and chat endpoints.

Requires a running API (local or staging). Example:

  uv run python scripts/load_test_chat.py \\
    --base-url http://localhost:8000 \\
    --token "$JWT" \\
    --conversation-id "$CONVERSATION_UUID" \\
    --workers 10 \\
    --requests 50
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import time
from uuid import UUID

import httpx


async def hit_health(client: httpx.AsyncClient) -> tuple[int, float]:
    start = time.perf_counter()
    response = await client.get("/api/v1/health")
    return response.status_code, time.perf_counter() - start


async def hit_chat(
    client: httpx.AsyncClient,
    conversation_id: UUID,
    token: str,
) -> tuple[int, float]:
    start = time.perf_counter()
    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "Resumen breve del expediente."},
        timeout=120.0,
    )
    return response.status_code, time.perf_counter() - start


async def worker(
    client: httpx.AsyncClient,
    *,
    conversation_id: UUID | None,
    token: str | None,
    requests_per_worker: int,
    results: list[tuple[str, int, float]],
    worker_id: int,
) -> None:
    for index in range(requests_per_worker):
        status, elapsed = await hit_health(client)
        results.append(("health", status, elapsed))

        if conversation_id and token:
            status, elapsed = await hit_chat(client, conversation_id, token)
            results.append(("chat", status, elapsed))

        if worker_id == 0 and index == 0:
            print(f"  first health OK ({elapsed * 1000:.0f} ms)", flush=True)


async def run_load_test(
    base_url: str,
    *,
    workers: int,
    total_requests: int,
    conversation_id: UUID | None,
    token: str | None,
) -> int:
    requests_per_worker = max(1, total_requests // workers)
    results: list[tuple[str, int, float]] = []

    limits = httpx.Limits(max_connections=workers * 2, max_keepalive_connections=workers)
    async with httpx.AsyncClient(base_url=base_url.rstrip("/"), limits=limits) as client:
        tasks = [
            worker(
                client,
                conversation_id=conversation_id,
                token=token,
                requests_per_worker=requests_per_worker,
                results=results,
                worker_id=i,
            )
            for i in range(workers)
        ]
        started = time.perf_counter()
        await asyncio.gather(*tasks)
        duration = time.perf_counter() - started

    by_kind: dict[str, list[tuple[int, float]]] = {}
    for kind, status, elapsed in results:
        by_kind.setdefault(kind, []).append((status, elapsed))

    print(f"\nCompleted {len(results)} requests in {duration:.2f}s "
          f"({len(results) / duration:.1f} req/s)\n")

    exit_code = 0
    for kind, entries in sorted(by_kind.items()):
        statuses = [status for status, _ in entries]
        latencies = [elapsed for _, elapsed in entries]
        ok = sum(1 for status in statuses if 200 <= status < 300)
        errors = len(statuses) - ok
        print(
            f"{kind}: {len(entries)} requests, {ok} OK, {errors} errors, "
            f"p50={statistics.median(latencies) * 1000:.0f}ms, "
            f"p95={sorted(latencies)[int(len(latencies) * 0.95) - 1] * 1000:.0f}ms"
        )
        if errors:
            exit_code = 1

    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="LexDictum API load test stub")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--token", help="JWT for chat requests (optional)")
    parser.add_argument("--conversation-id", help="Conversation UUID for chat (optional)")
    args = parser.parse_args()

    conversation_id = UUID(args.conversation_id) if args.conversation_id else None
    if bool(args.token) != bool(conversation_id):
        print("Provide both --token and --conversation-id for chat load, or omit both.")
        return 2

    print(
        f"Load test: {args.base_url}, workers={args.workers}, "
        f"~{args.requests} health requests"
        + (" + chat" if conversation_id else "")
    )

    return asyncio.run(
        run_load_test(
            args.base_url,
            workers=args.workers,
            total_requests=args.requests,
            conversation_id=conversation_id,
            token=args.token,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
