# OpenLDR Analytics API (Python/Flask)

## Overview

Central analytics API for the OpenLDR platform. Provides RESTful endpoints for laboratory test reporting and analytics. Built with Flask, Flask-RESTful, and SQLAlchemy connecting to SQL Server databases.

**Base URL**: `https://dev.openldr.org.mz` (dev) / `https://api.openldr.org.mz` (prod)
**Swagger UI**: Available at `/apidocs/`
**Port**: 9001 (production via Waitress) / 5000 (Docker)

## Technology Stack

- **Framework**: Flask 3.1.0 + Flask-RESTful 0.3.10
- **ORM**: SQLAlchemy 2.0.40 + Flask-SQLAlchemy 3.1.1
- **Auth**: Flask-JWT-Extended 4.7.1 (JWT tokens, 60min expiry)
- **Database**: SQL Server via pyodbc (ODBC Driver 17)
- **Docs**: Flasgger 0.9.7.1 (Swagger/OpenAPI)
- **Production**: Waitress 3.0.2 WSGI server
- **Data Processing**: Pandas 2.2.3

## Project Structure

```
api_openldr_python/
├── app.py                      # Main Flask app, route registration, config
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Docker config (python:3.12-slim)
├── docker-compose.yml          # Docker Compose (port 5000)
│
├── auth/                       # Authentication module
│   ├── routes.py               # Auth route registration
│   ├── auth_controller.py      # Login, CRUD, Clerk webhook endpoints
│   ├── auth_service.py         # Auth business logic (bcrypt, JWT)
│   └── user_model.py           # User & UserLogs SQLAlchemy models
│
├── configs/                    # Configuration
│   ├── paths.py                # Environment variables, DB connection strings
│   └── paths_local.py          # Local fallback configuration
│
├── db/                         # Database
│   └── database.py             # SQLAlchemy initialization (db = SQLAlchemy())
│
├── utilities/                  # Shared utilities
│   ├── utils.py                # Query helpers: date functions, aggregations, filters
│   └── swagger.py              # Swagger template & parameter definitions
│
├── dict/                       # Dictionary/Master data module
│   ├── routes.py
│   ├── controllers/            # laboratories_controller, facilities_controller
│   ├── models/                 # laboratories_model, facilities_model, hf_lat_long_model
│   └── services/               # laboratories_services, facilities_services
│
├── tb/                         # Tuberculosis module
│   ├── gxpert/                 # GeneXpert submodule (REFERENCE IMPLEMENTATION)
│   │   ├── routes.py           # 40+ endpoint registrations
│   │   ├── models/             # tb_gx_model.py (TBMaster - 118 columns)
│   │   ├── controllers/        # facility, laboratory, summary, patients
│   │   └── services/           # facility, laboratory, summary, patients
│   └── cultura/                # TB Culture (placeholder)
│
└── hiv/                        # HIV module
    ├── vl/                     # Viral Load
    │   ├── routes.py           # 45 routes: laboratories, facilities, summary, patients
    │   ├── models/             # vl.py (VlData - 150+ columns)
    │   ├── controllers/        # laboratory, facilities, summary
    │   └── services/           # laboratory, facilities, summary
    ├── dpi/                    # Early Infant Diagnosis (placeholder)
    │   ├── conv/               # Conventional testing
    │   └── poc/                # Point of Care testing
    └── ad/                     # Advanced Diseases (placeholder)
        ├── cd4/
        ├── crag/
        └── tblam/
```

## Module Pattern (MVC)

All modules follow the same architecture. **Use TB GeneXpert (`tb/gxpert/`) as the reference implementation** when creating new modules.

### Layer Responsibilities

1. **Models** (`models/`): SQLAlchemy ORM model definitions mapping to SQL Server tables
2. **Services** (`services/`): Business logic, database queries, data aggregation
3. **Controllers** (`controllers/`): Flask-RESTful Resource classes, request parsing, response formatting
4. **Routes** (`routes.py`): Maps URL paths to controller classes via Flask-RESTful API

### Adding a New Endpoint

```python
# 1. Model (models/my_model.py)
class MyModel(db.Model):
    __bind_key__ = 'my_bind'
    __tablename__ = 'MyTable'
    ID = db.Column(db.Integer, primary_key=True)
    # ... columns

# 2. Service (services/my_service.py)
def get_data(filters):
    query = db.session.query(MyModel.Field1, func.count().label('total'))
    query = query.filter(MyModel.DateField.between(start, end))
    return query.group_by(MyModel.Field1).all()

# 3. Controller (controllers/my_controller.py)
class MyEndpoint(Resource):
    @jwt_required()
    def get(self):
        args = request.args
        # Parse parameters, call service, return JSON
        return jsonify(result)

# 4. Routes (routes.py)
def my_routes(api):
    api.add_resource(MyEndpoint, '/module/endpoint/')
```

## Common Query Parameters

All reporting endpoints accept these standard parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `interval_dates` | JSON array | Date range: `["YYYY-MM-DD", "YYYY-MM-DD"]` |
| `province` | string(s) | Province name filter (multi-select) |
| `district` | string(s) | District name filter (multi-select) |
| `health_facility` | string | Specific facility name |
| `facility_type` | string | `"province"` \| `"district"` \| `"health_facility"` |
| `disaggregation` | string | `"True"` \| `"False"` |

## Database Binds

Configured in `configs/paths.py`. Each bind connects to a separate SQL Server database:

| Bind Key | Purpose |
|----------|---------|
| `vl` | HIV Viral Load data |
| `dpi` | HIV Early Infant Diagnosis (EID/DPI) |
| `ad` | HIV Advanced Diseases |
| `tb` | TB GeneXpert data |
| `dict` | Dictionary (facilities, laboratories) |
| `users` | User authentication data |
| `reportData` | Weekly VL lab reports (ReportData.Resume) |

## VL parity with the legacy API

The `hiv/vl/*` endpoints reproduce the numbers of the legacy Node API
(`openldr-backend`) that `cargaviral.openldr.org.mz` used. All counting rules
live in `hiv/vl/services/vl_common.py`. `tools/vl_parity_check.py` compares
both APIs on real data.

Deliberate differences from Node (✱):

| ✱ | Endpoints | Node | Python |
|---|---|---|---|
| Rejection codes | `facilities/rejected_samples_by_month/`, `facilities/rejected_samples_by_facility/` | Both `LIMSRejectionCode` and `HIVVL_LIMSRejectionCode` non-empty (AND) | Either non-empty (OR), like the lab and summary endpoints |
| Rejection window | same two endpoints | `RegisteredDatetime BETWEEN start AND end` (end day excluded after midnight) | `CAST(RegisteredDateTime AS DATE)` between start and end, both days included |
| TAT 90-day cap | every TAT endpoint | Intended a `< 90` days cap, but a duplicate object key dropped it | No cap, so the same numbers as Node actually produced |

Kept on purpose, for parity:
- Every other date filter is `col BETWEEN 'start' AND 'end'` on bare dates, so the end day counts only rows at midnight.
- TAT averages are integer `AVG(DATEDIFF(day, ...))`, so they truncate.
- `tested_samples`, `tat_by_lab` and `tat_by_month` (laboratories) default to `TestingFacilityCode LIKE 'P%'` when no `lab_code` or location filter is given. `tested_samples_by_month` and the rejection endpoints have no default.
- Facility endpoints exclude `RequestingProvinceName` NULL or `'null'` when no location is given, except `tested_samples_by_month` and `tested_samples_by_gender_by_month`.

VL-specific parameters: `lab_code` (repeatable or CSV), `age_range=min,max`.
Patient searches also take `province`, `district`, `pregnant`, `breastfeeding`,
`rejected`, `result_type` and `per_page` (maximum 500).

New endpoints:
- `summary/tat_vs_disalinks/`: static file `hiv/vl/data/tat_vs_disalinks.json`.
- `laboratories/weekly_report/` and `laboratories/weekly_report_national/`: ReportData `Resume`, bind `reportData`, env `DB_REPORT_DATA`.
- `facilities/tested_samples_pregnant_by_facility/` and `facilities/tested_samples_breastfeeding_by_facility/`.

Errors: services return `{"status": "error", "code": N}` and
`run_reporting_endpoint` sends HTTP N. 5xx bodies never include exception
text, and `InvalidParameter` gives a 400.

## Utility Functions (utilities/utils.py)

Key query builder helpers used across all modules:

- **Date extraction**: `YEAR()`, `MONTH()`, `DAY()`, `QUARTER()`, `WEEK()`
- **Aggregation**: `TOTAL_ALL`, `TOTAL_NOT_NULL(field)`, `TOTAL_NULL(field)`, `TOTAL_IN(field, values)`
- **Date differences**: `DATE_DIFF_AVG(fields)`, `DATE_DIFF_MIN(fields)`, `DATE_DIFF_MAX(fields)`
- **Conditional**: `SUPPRESSION(field, value)`, `GENDER_SUPPRESSION(fields, values)`
- **Filtering**: `LAB_TYPE(Model, lab_type)` - filter by Conventional/POC

## Authentication

- Every reporting endpoint authenticates through
  `utilities.controller_helpers.authenticate_request()`, which calls
  `utilities.token_verification.verify_bearer_token()`. Accepted tokens:
  - **Clerk session tokens** (RS256) from the dashboards — verified against
    `CLERK_JWTS_URL` (JWKS, cached; unknown `kid` refetched at most every 60 s),
    `CLERK_ISSUER`, expiry, and `CLERK_AUTHORIZED_PARTIES` (`azp`) when set.
  - **API login tokens** (HS256) from `POST /auth/login` — verified with the
    Flask/JWT secret; 60 min expiry.
- Anything else → HTTP 401 `{"status": "error", "code": 401, "message": "Invalid or missing token"}`.
  The reason is logged, never returned.
- If `CLERK_ISSUER` or `CLERK_JWTS_URL` is empty, all Clerk tokens are rejected
  (fail closed). Before changing Clerk config, check a real dashboard token
  with the target config (the token lives ~60 s, so run it right after copying;
  it is never printed):
  - bash: `python -m tools.check_clerk_token < token.txt`
  - PowerShell: `python -m tools.check_clerk_token token.txt`
    (or `Get-Content token.txt | python -m tools.check_clerk_token`)

  The tool also prints a "diagnostic (unverified)" clock offset (host time minus
  token `iat`); a large or negative value means the host clock is off
  (`w32tm /query /status`).
- On Windows the authorized-parties key is `[Clerk] clerk_authorized_parties` in `configs/configs.ini`.
- HS256 API tokens are rejected outright if the effective secret
  (`JWT_SECRET_KEY`, else `SECRET_KEY` from `FLASK_SECRET_KEY` /
  `[Flask] secret_key`) is unset, the default `"default-secret-key"`, or shorter
  than 32 bytes.
- API tokens come **only** from `POST /auth/login`. `POST /auth/clerk` is the
  Clerk webhook: every request must carry a valid Svix signature
  (`utilities/webhook_verification.py`, 5 min timestamp tolerance) and it never
  returns a token. `CLERK_WEBHOOK_SECRET_KEY` (`[Clerk] clerk_webhook_secret` on
  Windows) must equal the signing secret (`whsec_...`) of the Clerk webhook
  endpoint, otherwise the webhook rejects everything with 401.
- Role-based access: Admin and User roles (`utilities/auth_helpers.py`).

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (see configs/paths.py for required vars)
export FLASK_SECRET_KEY=...
export CDR_DOMAIN=...
export DB_USER=...
export DB_PASSWORD=...
# ... (see .env.example or configs/paths.py)

# Run development server
python app.py

# Production (Windows service via NSSM)
waitress-serve --host=127.0.0.1 --port=9001 app:app
```

## Naming Conventions

- **Files**: snake_case (e.g., `tb_gx_controller_facility.py`)
- **Classes**: PascalCase (e.g., `TBGxRegisteredSamplesByFacility`)
- **Functions**: snake_case (e.g., `get_registered_samples_by_facility`)
- **Routes**: lowercase with underscores (e.g., `/tb/gx/facilities/registered_samples/`)
- **Module prefix**: `/{domain}/{submodule}/{category}/{endpoint}/`
  - Example: `/tb/gx/facilities/registered_samples/`
  - Example: `/hiv/vl/laboratories/tested_samples/`
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenLDR API is a RESTful API for laboratory data management in Mozambique, built with Flask + Flask-RESTful. It serves TB GeneXpert and HIV Viral Load testing data with JWT authentication and Swagger documentation.

- **Production server:** Waitress on Windows (port 9001), managed by NSSM
- **Dev server:** Flask built-in (`python app.py`) or Gunicorn/Docker
- **API docs:** `http://localhost:5000/apidocs/` (Swagger UI)
- **Root redirects** to `/apidocs/`

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Development
python app.py

# Production (Linux/Docker)
gunicorn --bind 0.0.0.0:5000 app:app

# Production (Windows via Waitress)
waitress-serve --host=127.0.0.1 --port=9001 app:app
```

Tests run with `python -m pytest -q` (no database needed). No linter configuration exists.

## Environment Variables

All required variables must be set before running:

| Variable | Purpose |
|---|---|
| `FLASK_SECRET_KEY` | Flask session secret |
| `DB_USER` / `DB_PASSWORD` | SQL Server credentials (shared across all DBs) |
| `LOCAL_DOMAIN` / `CDR_DOMAIN` / `CLOUD_DOMAIN` | SQL Server hostnames per environment |
| `TB_DASHBOARD_DOMAIN` | TB dashboard server |
| `DB_VL_DATA`, `DB_DPI`, `DB_HIV_AD`, `DB_TB_DATA`, `DB_DICT`, `DB_USERS`, `DB_REPORT_DATA` | Database names |

The active environment binding is selected in `app.py` by assigning one of the three `SQLALCHEMY_BINDS_*` dicts from `configs/paths.py` to `app.config["SQLALCHEMY_BINDS"]`.

## Architecture

### Multi-Database Setup

The app connects to **7 SQL Server databases** simultaneously using SQLAlchemy binds. Each ORM model specifies which database it belongs to via `__bind_key__`:

- `vl` — HIV Viral Load data
- `dpi` — Drug Program Information
- `ad` — HIV Additional (CD4, CRAG, TBLAM)
- `tb` — TB GeneXpert data
- `dict` — Reference data (facilities/laboratories)
- `users` — Authentication & user logs
- `reportData` — Weekly VL lab reports (ReportData.Resume)

Connection strings use `mssql+pyodbc` with ODBC Driver 17 for SQL Server.

### Code Organization Pattern

Each feature module follows a strict 3-layer pattern:

```
feature/
├── routes.py          # Registers Flask-RESTful Resources onto the API object
├── controllers/       # Flask-RESTful Resource classes — parse args, call services, return JSON
├── services/          # Business logic — SQLAlchemy queries, data transformation
└── models/            # SQLAlchemy ORM model definitions
```

Request flow: `HTTP → routes.py → controller (reqparse) → service (SQLAlchemy) → SQL Server → JSON response`

### Module Structure

- `tb/gxpert/` — TB GeneXpert (most complete; 40+ endpoints across facility, laboratory, summary controllers)
- `hiv/vl/` — HIV Viral Load (laboratory, facility, summary, weekly and patient endpoints; parity with the legacy Node API)
- `hiv/ad/` — HIV Additional tests (CD4, CRAG, TBLAM; partially implemented)
- `dict/` — Reference data (laboratories and facilities, filterable by province/district)
- `auth/` — JWT authentication, user CRUD, login/logout logging
- `utilities/utils.py` — Shared SQL query builders, token helpers, parameter processors
- `utilities/swagger.py` — Swagger/OpenAPI template and parameter definitions
- `configs/paths.py` — Environment variable loading and SQLAlchemy bind dict definitions
- `db/database.py` — SQLAlchemy `db` instance (imported everywhere models need it)
- `app.py` — App factory: binds config, registers routes, initializes JWT/Swagger/CORS

### Authentication

- JWT tokens via `flask-jwt-extended`, 60-minute expiration
- Tokens obtained only via `POST /auth/login` (the `/auth/clerk` webhook never returns tokens)
- Role-based access: `Admin` role has elevated privileges in some endpoints
- Verified token claims are mapped to `session['user_info']` by `get_user_token_info()` in `authenticate_request()`; see the Authentication section above.

### Common API Parameters

Most endpoints share these query parameters (defined as reqparse arguments in controllers):
- `interval_dates` — JSON array `["YYYY-MM-DD", "YYYY-MM-DD"]`
- `province` / `district` — geographic filters
- `facility_type` — `province`, `district`, or `health_facility`
- `type_of_laboratory` — laboratory type filter
- `disaggregation` — boolean, enables disaggregated response
- `genexpert_result_type` — `Ultra 6 Cores` or `XDR 10 Cores`

Helper `PROCESS_COMMON_PARAMS_FACILITY()` and `PROCESS_COMMON_PARAMS_LABORATORY()` in `utilities/utils.py` parse and validate these consistently.

## Adding a New Endpoint

1. Add the SQLAlchemy model in `<module>/models/` with the correct `__bind_key__`
2. Add query logic in `<module>/services/`
3. Create a Flask-RESTful `Resource` class in `<module>/controllers/`
4. Register it in `<module>/routes.py` using `api.add_resource()`
5. Add the route function call in `app.py` if it's a new module

## Switching Environments

In `app.py`, change the active bind dict:
```python
# CDR (current production)
app.config["SQLALCHEMY_BINDS"] = SQLALCHEMY_BINDS_CDR_OPENLDR_ORG_MZ

# Local development
# app.config["SQLALCHEMY_BINDS"] = SQLALCHEMY_BINDS_APHL_OPENLDR_ORG_MZ

# Cloud
# app.config["SQLALCHEMY_BINDS"] = SQLALCHEMY_BINDS_CLOUD_QUEUE_OPENLDR_ORG_MZ
```

Alternatively, swap the import between `configs/paths.py` (production) and `configs/paths_local.py` (local dev).
