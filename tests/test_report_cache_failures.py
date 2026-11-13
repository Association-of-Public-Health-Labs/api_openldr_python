"""A corrupt or unwritable report cache must not change report outcomes."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from utilities import report_cache


URL = "/hiv/vl/summary/number_of_samples_by_month/"
TARGET = "hiv.vl.controllers.vl_controller_summary.number_of_samples_service_by_month"
KEY = {"path": URL, "window": report_cache.YEAR, "params": {}}
NOW = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_CACHE_DIR", str(tmp_path))
    return tmp_path


def envelope(**changes):
    return {"key": KEY, "computed_at": NOW.isoformat(), "data": [{"total": 7}], **changes}


def store_raw(entry):
    with open(report_cache._file(KEY), "w", encoding="utf-8") as handle:
        json.dump(entry, handle)


INVALID_ENTRIES = [
    None,
    [],
    "unexpected",
    5,
    envelope(key={**KEY, "path": "/hiv/eid/summary/indicators/"}),
    {name: value for name, value in envelope().items() if name != "key"},
    {name: value for name, value in envelope().items() if name != "data"},
    envelope(computed_at=None),
    envelope(computed_at=123),
    envelope(computed_at="2026-11-13T12:00:00"),
    envelope(computed_at="2026-11-13"),
    envelope(computed_at="not-a-timestamp"),
    envelope(data=None),
    envelope(data="unexpected"),
    envelope(data=123),
    envelope(data={"status": "error", "code": 500, "message": "failed"}),
]


@pytest.mark.parametrize("entry", INVALID_ENTRIES)
def test_corrupt_or_error_entries_are_cache_misses(cache_dir, entry):
    store_raw(entry)
    assert report_cache.read(KEY, now=NOW) is None


def test_future_timestamp_is_a_cache_miss(cache_dir):
    store_raw(envelope(computed_at=(NOW + timedelta(seconds=1)).isoformat()))
    assert report_cache.read(KEY, now=NOW) is None


def test_aware_non_utc_timestamp_is_supported(cache_dir):
    store_raw(envelope(computed_at=NOW.astimezone(timezone(timedelta(hours=2))).isoformat()))
    assert report_cache.read(KEY, now=NOW)["data"] == [{"total": 7}]


@pytest.mark.parametrize("data", [[], {}, {"data": [], "total": 0, "page": 1}])
def test_empty_and_paginated_successes_remain_cacheable(cache_dir, data):
    assert report_cache.write(KEY, data, now=NOW) is not None
    assert report_cache.read(KEY, now=NOW)["data"] == data


@pytest.mark.parametrize(
    "data",
    [None, "unexpected", 1, True, (1, 2), {"status": "error", "code": 503}],
)
def test_invalid_responses_cannot_replace_a_previous_success(cache_dir, data):
    report_cache.write(KEY, [{"total": 7}], now=NOW)
    assert report_cache.write(KEY, data, now=NOW) is None
    assert report_cache.read(KEY, now=NOW)["data"] == [{"total": 7}]
    assert all(path.suffix == ".json" for path in cache_dir.iterdir())


@pytest.mark.parametrize("fault", ["open", "serialize", "replace"])
def test_failed_atomic_write_preserves_existing_entry_and_removes_temporary_files(cache_dir, caplog, fault):
    report_cache.write(KEY, [{"total": 7}], now=NOW)
    original = next(cache_dir.iterdir()).read_bytes()

    def serialization_failure(entry, handle, **kwargs):
        handle.write('{"partial":')
        raise TypeError("private-cache-write-detail")

    target = {
        "open": "utilities.report_cache.os.fdopen",
        "serialize": "utilities.report_cache.json.dump",
        "replace": "utilities.report_cache.os.replace",
    }[fault]
    failure = serialization_failure if fault == "serialize" else OSError("private-cache-write-detail")
    with patch(target, side_effect=failure):
        assert report_cache.write(KEY, [{"total": 8}], now=NOW) is None

    assert list(cache_dir.glob("*.tmp")) == []
    assert len(list(cache_dir.iterdir())) == 1
    assert next(cache_dir.iterdir()).read_bytes() == original
    assert report_cache.read(KEY, now=NOW)["data"] == [{"total": 7}]
    assert "private-cache-write-detail" not in caplog.text


@pytest.mark.parametrize(
    "invalid_key",
    [None, [], {}, {**KEY, "path": None}, {**KEY, "window": "other"},
     {**KEY, "params": []}, {**KEY, "params": {"province": 5}}],
)
def test_warmup_ignores_records_with_invalid_keys(cache_dir, invalid_key):
    store_raw(envelope(key=invalid_key))
    assert report_cache.stored_keys() == []


@pytest.mark.parametrize("entry", [None, [], envelope(computed_at=None), envelope(data=None), envelope(data={"status": "error"})])
def test_warmup_ignores_invalid_envelopes(cache_dir, entry):
    store_raw(entry)
    assert report_cache.stored_keys() == []


def test_warmup_keeps_valid_stale_entries_for_recomputation(cache_dir):
    store_raw(envelope(computed_at=(datetime.now(timezone.utc) - timedelta(days=365)).isoformat()))
    assert report_cache.stored_keys() == [KEY]


@pytest.mark.parametrize("entry", [[], envelope(computed_at=None), envelope(data={"status": "error", "code": 500})])
def test_corrupt_cache_falls_back_to_live_report(app, auth_headers, cache_dir, monkeypatch, entry):
    monkeypatch.setitem(app.config, "REPORT_CACHE_ENABLED", True)
    if isinstance(entry, dict) and entry.get("computed_at") is not None:
        entry = {**entry, "computed_at": datetime.now(timezone.utc).isoformat()}
    store_raw(entry)
    with patch(TARGET, return_value=[{"total": 8}]) as service:
        response = app.test_client().get(
            URL, query_string={"interval_dates": report_cache.window_param(report_cache.YEAR)}, headers=auth_headers,
        )
    assert response.status_code == 200
    assert response.get_json() == [{"total": 8}]
    assert response.headers["X-Report-Cache"] == "MISS"
    service.assert_called_once()


def test_corrupt_cache_cannot_hide_live_service_failure(app, auth_headers, cache_dir, monkeypatch):
    monkeypatch.setitem(app.config, "REPORT_CACHE_ENABLED", True)
    store_raw(envelope(computed_at=datetime.now(timezone.utc).isoformat(), data={"status": "error", "code": 500}))
    with patch(TARGET, return_value={"status": "error", "code": 503, "message": "not available"}) as service:
        for _ in range(2):
            response = app.test_client().get(
                URL, query_string={"interval_dates": report_cache.window_param(report_cache.YEAR)}, headers=auth_headers,
            )
            assert response.status_code == 503
            assert "X-Report-Cache" not in response.headers
    assert service.call_count == 2
    with open(report_cache._file(KEY), encoding="utf-8") as handle:
        assert json.load(handle)["data"] == {"status": "error", "code": 500}
