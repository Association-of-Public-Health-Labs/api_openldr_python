import argparse
import os
import time

import requests


DEFAULT_ENDPOINTS = [
    "/tb/gx/summary/summary_header_component/",
    "/hiv/vl/summary/header_indicators_by_month/",
    "/hiv/vl/summary/viral_suppression_by_month/",
    "/hiv/eid/summary/indicators/",
    "/hiv/eid/laboratories/tested_samples_by_month/",
]


def _join_url(base_url, path):
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def _summarize_response(response):
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type.lower():
        try:
            payload = response.json()
        except ValueError:
            payload = response.text[:500]
    else:
        payload = response.text[:500]

    return {
        "status_code": response.status_code,
        "content_type": content_type,
        "body_preview": payload,
    }


def main():
    parser = argparse.ArgumentParser(description="Measure selected OpenLDR API endpoints.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("OPENLDR_API_URL", "http://127.0.0.1:5000"),
        help="API base URL. Defaults to OPENLDR_API_URL or localhost.",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("OPENLDR_API_TOKEN"),
        help="Bearer token. Defaults to OPENLDR_API_TOKEN.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.getenv("OPENLDR_API_TIMEOUT", "300")),
        help="Request timeout in seconds.",
    )
    parser.add_argument(
        "--interval-dates",
        default=os.getenv("OPENLDR_INTERVAL_DATES", "2025-08-11,2026-08-11"),
        help="interval_dates query value.",
    )
    parser.add_argument("endpoints", nargs="*", default=DEFAULT_ENDPOINTS)
    args = parser.parse_args()

    headers = {}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"

    for endpoint in args.endpoints:
        url = _join_url(args.base_url, endpoint)
        started = time.perf_counter()
        try:
            response = requests.get(
                url,
                headers=headers,
                params={"interval_dates": args.interval_dates},
                timeout=args.timeout,
            )
            elapsed = time.perf_counter() - started
            summary = _summarize_response(response)
            print(f"{endpoint} elapsed_seconds={elapsed:.3f}")
            print(summary)
        except requests.RequestException as exc:
            elapsed = time.perf_counter() - started
            print(f"{endpoint} elapsed_seconds={elapsed:.3f}")
            print({"status": "failed", "error_type": exc.__class__.__name__, "error": str(exc)})


if __name__ == "__main__":
    main()
