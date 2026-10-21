"""
Recompute the dashboards' default reports into the shared report cache.

Run it twice a day (Coolify scheduled task) and after each deploy, in the API container:

    python -m tools.warm_report_cache

It recomputes the seed reports (``tools/report_cache_seeds.py``) and every other entry already in
the cache, each over today's "last 12 months" window, through the endpoints themselves (same
parameters, same code path, same JSON). It runs in its own process, outside the web server: the
requests never leave it, and the token check is skipped only here because the warm-up asks for the
same aggregates any signed-in user would get (no patient lists, no Admin-only views).

Exit code 1 when any report failed, so the scheduler shows the run as failed.
"""

import json
import logging
import sys
import time
from unittest.mock import patch

logger = logging.getLogger("warm_report_cache")

WARMER_USER = "report-cache-warmer"


def _unique(keys):
    seen, out = set(), []
    for key in keys:
        marker = json.dumps(key, sort_keys=True)
        if marker not in seen:
            seen.add(marker)
            out.append(key)
    return out


def warm(app, keys):
    """Recompute ``keys``; returns (ok, failed) counts."""
    from utilities import controller_helpers, report_cache

    ok = failed = 0
    controller_helpers.FORCE_REFRESH = True
    try:
        with patch.object(controller_helpers, "authenticate_request", return_value=(WARMER_USER, None)):
            client = app.test_client()
            for key in keys:
                started = time.monotonic()
                response = client.get(key["path"], query_string=report_cache.query_for(key))
                seconds = time.monotonic() - started
                cached = response.headers.get("X-Report-Cache")
                if response.status_code == 200 and cached:
                    ok += 1
                    logger.info("ok     %5.1fs %s %s", seconds, key["path"], key["params"])
                else:
                    failed += 1
                    logger.error("FAILED %5.1fs %s %s -> HTTP %s", seconds, key["path"], key["params"], response.status_code)
    finally:
        controller_helpers.FORCE_REFRESH = False
    return ok, failed


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from app import app
    from tools.report_cache_seeds import seed_keys
    from utilities import report_cache

    if not report_cache.enabled():
        logger.warning("REPORT_CACHE_ENABLED=0: nothing to do.")
        return 0

    keys = _unique(seed_keys() + report_cache.stored_keys())
    logger.info("Warming %d reports into %s", len(keys), report_cache.cache_dir())
    started = time.monotonic()
    ok, failed = warm(app, keys)
    logger.info("Done in %.0fs: %d ok, %d failed", time.monotonic() - started, ok, failed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
