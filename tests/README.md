# OpenLDR_API Test Suite

Unit / contract tests for the Flask-RESTful endpoints exposed by
`hiv/vl`, `hiv/eid` and `tb/gxpert`. Every test mocks the service layer at
the controller import boundary so the suite **never** touches a real
database and runs in under two seconds.

## Layout

```
tests/
├── conftest.py              # shared fixtures (app, client, auth_headers, ...)
├── test_utils.py            # unit tests for utilities/utils.py helpers
├── hiv/
│   ├── test_vl_facility.py     # 14 routes
│   ├── test_vl_laboratory.py   # 12 routes
│   ├── test_vl_summary.py      # 6  routes
│   ├── test_eid_facility.py    # 8  routes
│   ├── test_eid_laboratory.py  # 6  routes
│   └── test_eid_summary.py     # 5  routes
└── tb/
    ├── test_tb_facility.py     # 20 routes
    ├── test_tb_laboratory.py   # 16 routes
    ├── test_tb_summary.py      # 6  routes
    └── test_tb_patients.py     # 4  routes (paginated)
```

`tests/test_hiv_endpoints.py` is a **standalone integration script** that
talks to real databases using a real JWT. It is intentionally excluded
from the pytest run via `collect_ignore` in `tests/conftest.py`. Run it
manually with `python tests/test_hiv_endpoints.py` if needed.

## Prerequisites

```powershell
# from the project root
python -m venv env
.\env\Scripts\activate
pip install -r requirements.txt
pip install pytest
```

## Running the suite

```powershell
# everything
.\env\Scripts\python.exe -m pytest -q

# only HIV
.\env\Scripts\python.exe -m pytest tests/hiv/ -q

# only TB
.\env\Scripts\python.exe -m pytest tests/tb/ -q

# a single file
.\env\Scripts\python.exe -m pytest tests/tb/test_tb_facility.py -v

# a single test, with full output
.\env\Scripts\python.exe -m pytest tests/tb/test_tb_patients.py::TestTbPatientsQueryParameters -vv -s
```

Useful flags:
- `-q` quiet, `-v` verbose, `-vv` very verbose
- `-x` stop on first failure
- `-k <expr>` only run tests whose name matches `<expr>`
- `--tb=short` / `--tb=line` shorter tracebacks

## Fixtures (defined in `tests/conftest.py`)

| Fixture | Scope | What it gives you |
| --- | --- | --- |
| `app` | session | Flask app with in-memory SQLite binds and routes registered for `vl`, `eid` and `tb_gxpert` |
| `client` | function | `app.test_client()` |
| `auth_token` | function | A valid JWT signed with the test secret |
| `auth_headers` | function | `{"Authorization": "Bearer <token>"}` |
| `mock_vl_service_response` | function | Sample VL row for response-shape assertions |
| `sample_query_params` | function | A typical VL/TB query string |
| `sample_eid_query_params` | function | A typical EID query string |

## Authoring a new endpoint test

The pattern is the same for every reporting endpoint:

```python
from unittest.mock import patch

def test_my_endpoint(client, auth_headers):
    with patch(
        "hiv.vl.controllers.vl_controller_facility.facility_registered_samples_service",
        return_value=[{"requesting_facility": "X", "total": 1}],
    ):
        r = client.get("/hiv/vl/facilities/registered_samples/", headers=auth_headers)
        assert r.status_code == 200
        assert r.get_json()[0]["requesting_facility"] == "X"
```

Important rules:
1. **Patch the symbol where it is used** (the controller module), not where
   it is defined. `vl_controller_facility.facility_registered_samples_service`,
   not `hiv.vl.services.vl_services_facilities.facility_registered_samples_service`.
2. Every reporting endpoint verifies the bearer token and returns 401 {"status": "error", "code": 401, "message": "Invalid or missing token"} when it is missing or untrusted. Use the auth_headers fixture for authenticated calls; tests/test_auth_enforcement.py covers the 401 contract.
3. Patient endpoints return a paginated envelope
   (`status / page / per_page / total_count / total_pages / data`), all
   other endpoints return a list (or, in a couple of summary cases, a
   single dict).

## Troubleshooting

- **`ModuleNotFoundError: flask_restful`** — activate the virtualenv first
  (`.\env\Scripts\activate`) or invoke pytest through
  `.\env\Scripts\python.exe -m pytest`.
- **`AttributeError: module ... does not have the attribute X`** —
  `unittest.mock.patch` could not find `X` on the controller module. The
  service was probably renamed or is imported under a different name; open
  the controller and copy the actual import.
