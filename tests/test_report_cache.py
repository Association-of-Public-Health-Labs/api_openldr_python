"""Shared cache of the dashboards' default reports (utilities/report_cache.py)."""
import json
import os
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from utilities import controller_helpers, report_cache
from utilities.report_cache import MONTHS, YEAR

TODAY = date(2026, 10, 21)
URL = "/hiv/vl/summary/number_of_samples_by_month/"
TARGET = "hiv.vl.controllers.vl_controller_summary.number_of_samples_service_by_month"


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_CACHE_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def cached_app(app, cache_dir, monkeypatch):
    """The test app with the cache on (it is off in tests by default)."""
    monkeypatch.setitem(app.config, "REPORT_CACHE_ENABLED", True)
    return app


def today_window():
    return report_cache.window_param(YEAR)


# --------------------------------------------------------------------------- windows


class TestDefaultWindow:
    def test_vl_window_same_day_last_year(self):
        assert report_cache.default_window(["2025-10-21,2026-10-21"], TODAY) == YEAR

    def test_tb_writes_a_space_after_the_comma(self):
        assert report_cache.default_window(["2025-10-21, 2026-10-21"], TODAY) == YEAR

    def test_tb_laboratory_window_first_of_the_month(self):
        assert report_cache.default_window(["2025-11-01,2026-10-21"], TODAY) == MONTHS

    def test_a_day_of_drift_from_the_browser_timezone(self):
        assert report_cache.default_window(["2025-10-20,2026-10-20"], TODAY) == YEAR
        assert report_cache.default_window(["2025-10-31,2026-10-21"], TODAY) == MONTHS

    def test_two_separate_values(self):
        assert report_cache.default_window(["2025-10-21", "2026-10-21"], TODAY) == YEAR

    @pytest.mark.parametrize(
        "values",
        [["2025-01-01,2025-12-31"], ["2025-10-18,2026-10-21"], ["oops"], [], None, ["2025-10-21,2026-10-21,2026-10-22"]],
    )
    def test_anything_else_is_not_a_default_window(self, values):
        assert report_cache.default_window(values, TODAY) is None

    def test_29_february_falls_back_to_the_28th(self):
        assert report_cache.window_dates(YEAR, date(2028, 2, 29)) == (date(2027, 2, 28), date(2028, 2, 29))

    def test_months_window_crosses_the_year(self):
        assert report_cache.window_dates(MONTHS, date(2026, 3, 15)) == (date(2025, 4, 1), date(2026, 3, 15))


# --------------------------------------------------------------------------- keys


class TestCacheKey:
    def args(self, **extra):
        return {"interval_dates": ["2025-10-21,2026-10-21"], **extra}

    def test_key_leaves_out_the_dates(self):
        a = report_cache.cache_key(URL, self.args(facility_type=["province"]), TODAY)
        b = report_cache.cache_key(URL, {"interval_dates": ["2025-10-20,2026-10-20"], "facility_type": ["province"]}, TODAY)
        assert a == b == {"path": URL, "window": YEAR, "params": {"facility_type": ["province"]}}

    def test_tb_reports_are_cached_too(self):
        assert report_cache.cache_key("/tb/gx/facilities/tested_samples/", self.args(), TODAY) is not None

    def test_eid_default_window_is_cacheable(self):
        key = report_cache.cache_key("/hiv/eid/summary/indicators/", self.args(lab_type=["poc"]), TODAY)
        assert key == {"path": "/hiv/eid/summary/indicators/", "window": YEAR, "params": {"lab_type": ["poc"]}}

    def test_eid_lab_filter_stays_live(self):
        assert report_cache.cache_key("/hiv/eid/summary/indicators/", self.args(lab_code=["PCD"]), TODAY) is None

    @pytest.mark.parametrize("name", ["province", "district", "health_facility", "lab_code"])
    def test_user_filters_stay_live(self, name):
        assert report_cache.cache_key(URL, self.args(**{name: ["Gaza"]}), TODAY) is None

    def test_single_facility_level_is_never_cached(self):
        assert report_cache.cache_key(URL, self.args(facility_type=["health_facility"]), TODAY) is None

    @pytest.mark.parametrize("path", ["/hiv/vl/patients/by_facility/", "/tb/gx/patients/by_name/", "/dict/facilities/", "/auth/login"])
    def test_patients_and_other_modules_are_never_cached(self, path):
        assert report_cache.cache_key(path, self.args(), TODAY) is None

    def test_another_period_stays_live(self):
        assert report_cache.cache_key(URL, {"interval_dates": ["2024-01-01,2024-12-31"]}, TODAY) is None

    def test_query_for_rebuilds_todays_window(self):
        key = {"path": URL, "window": MONTHS, "params": {"genexpert_result_type": ["Ultra 6 Cores"]}}
        assert report_cache.query_for(key, TODAY) == [
            ("genexpert_result_type", "Ultra 6 Cores"),
            ("interval_dates", "2025-11-01,2026-10-21"),
        ]


# --------------------------------------------------------------------------- store


class TestStore:
    KEY = {"path": URL, "window": YEAR, "params": {}}

    def test_write_then_read(self, cache_dir):
        report_cache.write(self.KEY, [{"total": 5}])
        assert report_cache.read(self.KEY)["data"] == [{"total": 5}]
        assert report_cache.stored_keys() == [self.KEY]

    def test_an_old_entry_is_not_served(self, cache_dir, monkeypatch):
        monkeypatch.setenv("REPORT_CACHE_MAX_AGE_HOURS", "24")
        report_cache.write(self.KEY, [1], now=datetime.now(timezone.utc) - timedelta(hours=25))
        assert report_cache.read(self.KEY) is None

    def test_a_broken_file_is_a_miss(self, cache_dir):
        report_cache.write(self.KEY, [1])
        (name,) = [n for n in os.listdir(cache_dir) if n.endswith(".json")]
        (cache_dir / name).write_text("{not json")
        assert report_cache.read(self.KEY) is None
        assert report_cache.stored_keys() == []

    def test_no_temporary_files_left_behind(self, cache_dir):
        report_cache.write(self.KEY, [1])
        assert all(n.endswith(".json") for n in os.listdir(cache_dir))

    def test_an_unwritable_cache_does_not_raise(self, monkeypatch, tmp_path):
        blocker = tmp_path / "file"
        blocker.write_text("x")
        monkeypatch.setenv("REPORT_CACHE_DIR", str(blocker / "sub"))
        assert report_cache.write(self.KEY, [1]) is None


# --------------------------------------------------------------------------- endpoint


class TestEndpoint:
    def test_default_report_is_computed_once_then_served_from_the_cache(self, cached_app, auth_headers):
        client = cached_app.test_client()
        query = {"interval_dates": today_window()}
        with patch(TARGET, return_value=[{"total": 7}]) as service:
            first = client.get(URL, query_string=query, headers=auth_headers)
            second = client.get(URL, query_string=query, headers=auth_headers)
        assert service.call_count == 1
        assert first.headers["X-Report-Cache"] == "MISS"
        assert second.headers["X-Report-Cache"] == "HIT"
        assert second.get_json() == first.get_json() == [{"total": 7}]
        assert second.headers["X-Report-Computed-At"] == first.headers["X-Report-Computed-At"]

    def test_the_cache_never_answers_without_a_valid_token(self, cached_app, auth_headers):
        client = cached_app.test_client()
        query = {"interval_dates": today_window()}
        with patch(TARGET, return_value=[{"total": 7}]):
            client.get(URL, query_string=query, headers=auth_headers)
            response = client.get(URL, query_string=query)
        assert response.status_code == 401
        assert "X-Report-Cache" not in response.headers

    def test_errors_are_not_cached(self, cached_app, auth_headers):
        client = cached_app.test_client()
        query = {"interval_dates": today_window()}
        with patch(TARGET, return_value={"status": "error", "code": 500, "message": "x"}) as service:
            client.get(URL, query_string=query, headers=auth_headers)
            client.get(URL, query_string=query, headers=auth_headers)
        assert service.call_count == 2

    def test_another_period_is_computed_every_time(self, cached_app, auth_headers):
        client = cached_app.test_client()
        with patch(TARGET, return_value=[]) as service:
            for _ in range(2):
                response = client.get(URL, query_string={"interval_dates": "2024-01-01,2024-12-31"}, headers=auth_headers)
        assert service.call_count == 2
        assert "X-Report-Cache" not in response.headers

    def test_off_in_tests_unless_asked(self, app, cache_dir, auth_headers):
        with patch(TARGET, return_value=[]) as service:
            for _ in range(2):
                app.test_client().get(URL, query_string={"interval_dates": today_window()}, headers=auth_headers)
        assert service.call_count == 2


# --------------------------------------------------------------------------- warm-up


class TestWarmUp:
    def test_recomputes_even_a_fresh_entry_without_a_token(self, cached_app, auth_headers):
        from tools.warm_report_cache import warm

        key = {"path": URL, "window": YEAR, "params": {}}
        report_cache.write(key, [{"total": 1}])
        with patch(TARGET, return_value=[{"total": 2}]):
            ok, failed = warm(cached_app, [key])
        assert (ok, failed) == (1, 0)
        assert report_cache.read(key)["data"] == [{"total": 2}]
        # Back to normal afterwards: requests read the cache again and need a token.
        assert controller_helpers.FORCE_REFRESH is False
        assert cached_app.test_client().get(URL, query_string={"interval_dates": today_window()}).status_code == 401

    def test_counts_failures(self, cached_app):
        from tools.warm_report_cache import warm

        with patch(TARGET, return_value={"status": "error", "code": 500, "message": "x"}):
            assert warm(cached_app, [{"path": URL, "window": YEAR, "params": {}}]) == (0, 1)

    def test_every_seed_is_a_cacheable_request_with_the_same_key(self):
        from tools.report_cache_seeds import seed_keys

        keys = seed_keys()
        assert len({json.dumps(k, sort_keys=True) for k in keys}) == len(keys)
        for key in keys:
            args = {}
            for name, value in report_cache.query_for(key, TODAY):
                args.setdefault(name, []).append(value)
            assert report_cache.cache_key(key["path"], args, TODAY) == key


def test_eid_seed_keys_are_cacheable():
    from tools.report_cache_seeds import EID_SEEDS, seed_keys

    assert EID_SEEDS
    keys = seed_keys()
    for path, window, params in EID_SEEDS:
        assert path.startswith("/hiv/eid/") and "/patients/" not in path
        # The dashboard's default request: no lab_type, no category (API defaults all / 0).
        assert "lab_type" not in params and "category" not in params
        args = {name: list(values) for name, values in params.items()}
        args["interval_dates"] = [report_cache.window_param(window, TODAY)]
        key = report_cache.cache_key(path, args, TODAY)
        assert key is not None, path
        assert key in keys, path


def test_eid_seeds_cover_every_card_default():
    from tools.report_cache_seeds import EID_SEEDS

    paths = {path for path, _, _ in EID_SEEDS}
    assert len(paths) == len(EID_SEEDS) == 28
    facility = [params for path, _, params in EID_SEEDS if "/facilities/" in path]
    assert facility and all(p == {"facility_type": ["province"], "disaggregation": ["false"]} for p in facility)


def test_eid_seed_paths_are_routes(app):
    from tools.report_cache_seeds import EID_SEEDS

    routes = {rule.rule for rule in app.url_map.iter_rules()}
    assert {path for path, _, _ in EID_SEEDS} <= routes


def test_viewport_requests_are_never_cached():
    args = {"interval_dates": ["2025-10-21,2026-10-21"], "viewport": ["-26,32,-10,41"]}
    assert report_cache.cache_key("/hiv/eid/laboratories/sample_routes_viewport/", args, TODAY) is None
