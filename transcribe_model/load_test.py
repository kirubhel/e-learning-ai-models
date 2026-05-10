"""
load_test.py — Concurrent load test for POST /api/games/transcribe (Go backend).

The script sends real audio files through the full API stack:
    load_test.py → Go API /api/games/transcribe → transcribe-service:9022/evaluate

Usage examples:
    # With a pre-obtained JWT token
    python load_test.py --audio hello.wav --token <jwt> --users 20 --word "hello"

    # With auto-login (phone + OTP)
    python load_test.py --audio hello.wav --phone "+251911000000" --otp "1234" --users 20

    # Target production
    python load_test.py --audio hello.wav --token <jwt> --users 50 \
        --base-url https://learningcloud.et --output report.json
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Dependency check — aiohttp
# ---------------------------------------------------------------------------
try:
    import aiohttp
except ImportError:
    print("❌  aiohttp is required. Install it with: pip install aiohttp")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_BASE_URL = "https://learningcloud.et"
DEFAULT_WORD = "hello"
DEFAULT_USERS = 10
DEFAULT_REPEAT = 1
DEFAULT_TIMEOUT = 60
DEFAULT_RAMP_UP = 0

TRANSCRIBE_PATH = "/api/games/transcribe"
LOGIN_PATH = "/api/auth/student-login"

RESET = "\033[0m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"


# ---------------------------------------------------------------------------
# Section 1: Auth helper
# ---------------------------------------------------------------------------
async def fetch_jwt(session: aiohttp.ClientSession, base_url: str,
                    username: str, otp: Optional[str]) -> Optional[str]:
    """Login via student-login/ and return the JWT access token."""
    url = base_url.rstrip("/") + LOGIN_PATH
    payload = {"username": username, "otp_code": otp or ""}
    try:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            body = await resp.json()
            token = (
                body.get("data", {}).get("access_token")
                or body.get("data", {}).get("token")
                or body.get("token")
                or body.get("access_token")
            )
            if not token:
                print(f"{RED}❌  Login failed (HTTP {resp.status}): {json.dumps(body)}{RESET}")
                return None
            print(f"{GREEN}✅  Login successful — JWT obtained for {username}.{RESET}")
            return token
    except Exception as exc:
        print(f"{RED}❌  Login request error: {exc}{RESET}")
        return None


# ---------------------------------------------------------------------------
# Section 2: Single request worker
# ---------------------------------------------------------------------------
async def send_request(
    session: aiohttp.ClientSession,
    base_url: str,
    audio_bytes: bytes,
    audio_filename: str,
    target_word: str,
    jwt_token: str,
    user_id: int,
    request_index: int,
    timeout: int,
) -> dict:
    """Send one POST /api/games/transcribe request and return a result dict."""
    url = base_url.rstrip("/") + TRANSCRIBE_PATH
    headers = {"Authorization": f"Bearer {jwt_token}"}
    start_at = time.monotonic()

    try:
        form = aiohttp.FormData()
        form.add_field(
            "audio_file",
            audio_bytes,
            filename=audio_filename,
            content_type="audio/wav",
        )
        form.add_field("target_word", target_word)

        request_timeout = aiohttp.ClientTimeout(total=timeout)
        async with session.post(url, data=form, headers=headers,
                                timeout=request_timeout) as resp:
            latency = time.monotonic() - start_at
            body = await resp.json(content_type=None)

            if resp.status == 200:
                overall_score = body.get("overall_score", body.get("score", 0))
                input_type = body.get("input_type", "—")
                details = body.get("details", [])
                first_status = details[0].get("status", "—") if details else "—"
                return {
                    "user_id": user_id,
                    "request_index": request_index,
                    "status_code": resp.status,
                    "latency": round(latency, 3),
                    "score": overall_score,
                    "input_type": input_type,
                    "eval_status": first_status,
                    "error": None,
                }
            else:
                error_msg = (
                    body.get("message") or body.get("error") or str(body)
                )[:100]
                return {
                    "user_id": user_id,
                    "request_index": request_index,
                    "status_code": resp.status,
                    "latency": round(latency, 3),
                    "score": None,
                    "input_type": None,
                    "eval_status": None,
                    "error": error_msg,
                }

    except asyncio.TimeoutError:
        latency = time.monotonic() - start_at
        return {
            "user_id": user_id,
            "request_index": request_index,
            "status_code": None,
            "latency": round(latency, 3),
            "score": None,
            "input_type": None,
            "eval_status": None,
            "error": f"Timeout after {timeout}s",
        }
    except Exception as exc:
        latency = time.monotonic() - start_at
        return {
            "user_id": user_id,
            "request_index": request_index,
            "status_code": None,
            "latency": round(latency, 3),
            "score": None,
            "input_type": None,
            "eval_status": None,
            "error": str(exc)[:100],
        }


# ---------------------------------------------------------------------------
# Section 3: User worker (repeats N times)
# ---------------------------------------------------------------------------
async def user_worker(
    session: aiohttp.ClientSession,
    base_url: str,
    audio_bytes: bytes,
    audio_filename: str,
    target_word: str,
    jwt_token: str,
    user_id: int,
    repeat: int,
    timeout: int,
    ramp_delay: float,
    results_list: list,
) -> None:
    """Simulates one virtual user who sends `repeat` requests sequentially."""
    if ramp_delay > 0:
        await asyncio.sleep(ramp_delay)

    for i in range(repeat):
        result = await send_request(
            session, base_url, audio_bytes, audio_filename,
            target_word, jwt_token, user_id, i + 1, timeout,
        )
        results_list.append(result)
        _print_row(result)


# ---------------------------------------------------------------------------
# Section 4: Result printer
# ---------------------------------------------------------------------------
def _result_color(result: dict) -> str:
    if result["error"]:
        return RED
    if result["score"] is not None and result["score"] >= 80:
        return GREEN
    if result["score"] is not None and result["score"] >= 50:
        return YELLOW
    return RED


def _print_header(total_requests: int, url: str) -> None:
    print(f"\n{BOLD}{CYAN}🚀  Starting load test — {total_requests} requests → {url}{RESET}")
    print("─" * 72)
    print(f"  {'#':>4}  {'User':>4}  {'Status':>6}  {'Score':>6}  {'Latency':>8}  Details")
    print("─" * 72)


_row_counter = 0


def _print_row(result: dict) -> None:
    global _row_counter
    _row_counter += 1
    color = _result_color(result)

    status = str(result["status_code"]) if result["status_code"] else "ERR"
    score_str = f"{result['score']:.1f}" if result["score"] is not None else "—"
    latency_str = f"{result['latency']:.2f}s"
    detail = (
        f"{result['input_type']} | {result['eval_status']}"
        if not result["error"]
        else f"ERROR: {result['error']}"
    )
    print(
        f"{color}  {_row_counter:>4}  "
        f"{result['user_id']:>4}  "
        f"{status:>6}  "
        f"{score_str:>6}  "
        f"{latency_str:>8}  "
        f"{detail}{RESET}"
    )


# ---------------------------------------------------------------------------
# Section 5: Summary builder
# ---------------------------------------------------------------------------
def build_summary(results: list, total_duration: float) -> dict:
    """Compute and return a summary dict from all results."""
    succeeded = [r for r in results if r["error"] is None and r["status_code"] == 200]
    failed = [r for r in results if r["error"] is not None or r["status_code"] != 200]

    latencies = [r["latency"] for r in results]
    scores = [r["score"] for r in succeeded if r["score"] is not None]

    sorted_latencies = sorted(latencies)
    count = len(sorted_latencies)

    def percentile(lst: list, pct: float) -> float:
        if not lst:
            return 0.0
        idx = max(0, int(len(lst) * pct / 100) - 1)
        return round(lst[idx], 3)

    return {
        "total_requests": len(results),
        "succeeded": len(succeeded),
        "failed": len(failed),
        "success_rate_pct": round(100 * len(succeeded) / len(results), 1) if results else 0,
        "total_duration_sec": round(total_duration, 2),
        "avg_latency_sec": round(sum(latencies) / count, 3) if count else 0,
        "min_latency_sec": round(min(latencies), 3) if latencies else 0,
        "max_latency_sec": round(max(latencies), 3) if latencies else 0,
        "p50_latency_sec": percentile(sorted_latencies, 50),
        "p95_latency_sec": percentile(sorted_latencies, 95),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
    }


def print_summary(summary: dict) -> None:
    width = 72
    print("\n" + "─" * width)
    print(f"{BOLD}✅  SUMMARY{RESET}")
    print(f"  Total requests     : {summary['total_requests']}")
    success_color = GREEN if summary['success_rate_pct'] >= 90 else YELLOW
    print(
        f"  Succeeded          : {success_color}{summary['succeeded']}"
        f"  ({summary['success_rate_pct']}%){RESET}"
    )
    fail_color = RED if summary['failed'] > 0 else GREEN
    print(f"  Failed             : {fail_color}{summary['failed']}{RESET}")
    print(f"  Total duration     : {summary['total_duration_sec']}s")
    print(f"  Avg latency        : {summary['avg_latency_sec']}s")
    print(f"  Min latency        : {summary['min_latency_sec']}s")
    print(f"  Max latency        : {summary['max_latency_sec']}s")
    print(f"  p50 latency        : {summary['p50_latency_sec']}s")
    print(f"  p95 latency        : {summary['p95_latency_sec']}s")
    if summary['avg_score'] > 0:
        print(f"  Avg score (ok)     : {summary['avg_score']} / 100")
    print("─" * width)


# ---------------------------------------------------------------------------
# Section 6: Main runner
# ---------------------------------------------------------------------------
async def run_load_test(args: argparse.Namespace) -> None:
    # --- Validate audio file
    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"{RED}❌  Audio file not found: {audio_path}{RESET}")
        sys.exit(1)
    audio_bytes = audio_path.read_bytes()
    audio_filename = audio_path.name
    print(f"🎵  Audio file : {audio_path} ({len(audio_bytes):,} bytes)")

    connector = aiohttp.TCPConnector(limit=args.users + 10)
    async with aiohttp.ClientSession(connector=connector) as session:
        # --- Obtain JWT
        if not args.token:
            username = args.phone or args.student_id
            if not username:
                print(f"{RED}❌  --token, --phone, or --student-id must be provided.{RESET}")
                sys.exit(1)
            
            # If phone is used, OTP is mandatory in script (unless it's developer env)
            if args.phone and not args.otp:
                 print(f"{YELLOW}⚠️  Warning: Phone login usually requires --otp.{RESET}")

            async with aiohttp.ClientSession() as login_session:
                token = await fetch_jwt(login_session, args.base_url, username, args.otp)
                if not token:
                    sys.exit(1)
                jwt_token = token
        else:
            jwt_token = args.token

        total_requests = args.users * args.repeat
        endpoint = args.base_url.rstrip("/") + TRANSCRIBE_PATH
        _print_header(total_requests, endpoint)

        results: list = []
        start_ts = time.monotonic()

        # Compute per-user ramp delay
        ramp = args.ramp_up / args.users if args.users > 1 and args.ramp_up > 0 else 0

        tasks = [
            asyncio.create_task(
                user_worker(
                    session, args.base_url, audio_bytes, audio_filename,
                    args.word, jwt_token, uid + 1,
                    args.repeat, args.timeout, ramp * uid, results,
                )
            )
            for uid in range(args.users)
        ]

        await asyncio.gather(*tasks)

        total_duration = time.monotonic() - start_ts
        summary = build_summary(results, total_duration)
        print_summary(summary)

        # --- Save JSON report
        if args.output:
            report = {"summary": summary, "results": results}
            out_path = Path(args.output)
            out_path.write_text(json.dumps(report, indent=2))
            print(f"\n📄  Report saved to: {out_path.resolve()}")


# ---------------------------------------------------------------------------
# Section 7: CLI entrypoint
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="load_test.py",
        description=(
            "Load test for POST /api/games/transcribe (Go API → AI transcribe model)."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--audio", required=True, metavar="FILE",
        help="Path to a .wav or .webm audio file to send in every request.",
    )
    parser.add_argument(
        "--word", default=DEFAULT_WORD, metavar="TEXT",
        help="target_word form field value.",
    )
    parser.add_argument(
        "--users", type=int, default=DEFAULT_USERS, metavar="N",
        help="Number of concurrent virtual users.",
    )
    parser.add_argument(
        "--repeat", type=int, default=DEFAULT_REPEAT, metavar="N",
        help="Number of sequential requests per user.",
    )
    parser.add_argument(
        "--ramp-up", type=float, default=DEFAULT_RAMP_UP, dest="ramp_up", metavar="SECS",
        help="Seconds over which to gradually spawn all users.",
    )
    parser.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT, metavar="SECS",
        help="Per-request timeout in seconds.",
    )
    parser.add_argument(
        "--base-url", default=DEFAULT_BASE_URL, dest="base_url", metavar="URL",
        help="API base URL (e.g. https://learningcloud.et).",
    )
    parser.add_argument("--token", metavar="JWT", help="Bearer JWT token. If omitted, login info must be provided.")
    parser.add_argument("--phone", metavar="PHONE", help="Student phone number for auto-login.")
    parser.add_argument("--student-id", metavar="ID", help="Student ID for auto-login (skips OTP).")
    parser.add_argument("--otp", metavar="OTP", help="OTP for auto-login (required for phone).")
    parser.add_argument("--output", metavar="FILE", help="Save full JSON report to this file.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_load_test(args))
