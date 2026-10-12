# OpenLDR API

A RESTful API for epidemiological and laboratory reporting, with endpoints for Tuberculosis (TB) GeneXpert, HIV Viral Load (VL), HIV EID, dictionary data, and user authentication.

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [API Documentation](#api-documentation)
  - [Active Route Modules](#active-route-modules)
  - [Authentication Endpoints](#authentication-endpoints)
  - [Tuberculosis GeneXpert Endpoints](#tuberculosis-genexpert-endpoints)
  - [HIV Viral Load Endpoints](#hiv-viral-load-endpoints)
  - [HIV EID Endpoints](#hiv-eid-endpoints)
  - [Dictionary Endpoints](#dictionary-endpoints)
- [Common Parameters](#common-parameters)
- [Pagination](#pagination)
- [Authentication](#authentication)
- [Getting Started](#getting-started)
- [Deployment](#deployment)
- [Environment Setup](#environment-setup)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Error Handling](#error-handling)

## Overview

The OpenLDR API provides REST endpoints for analytics and reporting across Tuberculosis GeneXpert (TB GX), HIV Viral Load (VL), HIV EID, dictionary/reference data, and authentication. The API includes JWT-based authentication, Clerk webhook integration, Swagger documentation via Flasgger, and patient endpoints with pagination.

## Project Structure

```
OpenLDR_API/
├── app.py                     # Entry point / route registration
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Container image
├── docker-compose.yml         # Local container orchestration
├── auth/                      # JWT + Clerk authentication module
├── tb/gxpert/                 # TB GeneXpert endpoints/controllers/services/models
├── hiv/vl/                    # HIV Viral Load endpoints/controllers/services/models
├── hiv/eid/                   # HIV EID endpoints/controllers/services/models
├── dict/                      # Dictionary/reference data endpoints
├── db/database.py             # SQLAlchemy instance
├── utilities/                 # Shared utilities + Swagger template
├── configs/
│   ├── paths.py               # Config loader + SQLAlchemy binds
│   ├── configs.ini            # Windows/local config source (gitignored)
│   └── configs.zip            # Backup config archive
├── tests/                     # Pytest and integration tests
└── docs/                      # Additional docs
```

## Tech Stack

### Core Framework
- **Flask 3.1.0** - Web framework
- **Flask-RESTful 0.3.10** - REST API extensions
- **Flask-SQLAlchemy 3.1.1** - Database ORM
- **SQLAlchemy 2.0.40** - Core database toolkit

### Authentication & Security
- **Flask-JWT-Extended 4.7.1** - JWT authentication
- **bcrypt 4.3.0** - Password hashing
- **PyJWT 2.10.1** - JWT handling
- **cryptography 45.0.6** - Cryptographic operations

### Database & Data Processing
- **pyodbc 5.2.0** - SQL Server database driver
- **pandas 2.2.3** - Data manipulation
- **numpy 2.2.4** - Numerical computing
- **openpyxl 3.1.5** - Excel file handling

### API Documentation & CORS
- **flasgger 0.9.7.1** - Swagger UI documentation
- **Flask-CORS 5.0.1** - Cross-origin resource sharing

### External Integrations
- **requests 2.32.3** - HTTP client
- **httpx 0.28.1** - Async HTTP client
- **google-generativeai 0.3.2** - Google AI integration
- **deep-translator 1.11.4** - Translation services

### Production & Deployment
- **gunicorn 23.0.0** - WSGI HTTP server
- **waitress 3.0.2** - WSGI server
- **Docker** - Containerization

### Development & Utilities
- **python-dateutil 2.9.0** - Date/time utilities
- **PyYAML 6.0.2** - YAML parsing
- **beautifulsoup4 4.13.3** - HTML/XML parsing
- **tqdm 4.67.1** - Progress bars

## API Documentation

### Active Route Modules

The API currently registers the following route modules in `app.py`:

| Module | Prefix | Route file |
|--------|--------|------------|
| Authentication | `/auth/*` | `auth/routes.py` |
| Dictionary | `/dict/*` | `dict/routes.py` |
| TB GeneXpert | `/tb/gx/*` | `tb/gxpert/routes.py` |
| HIV Viral Load | `/hiv/vl/*` | `hiv/vl/routes.py` |
| HIV EID | `/hiv/eid/*` | `hiv/eid/routes.py` |

> Note: `tb/cultura` exists in the repository but is not currently registered in `app.py`.

### Authentication Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/auth/login` | Login with username and password, returns JWT token | No |
| `POST` | `/auth/create` | Create a new user (Admin only) | Yes (JWT) |
| `PUT` | `/auth/update` | Update user details (Admin only) | Yes (JWT) |
| `DELETE` | `/auth/delete` | Delete a user (Admin only) | Yes (JWT) |
| `GET` | `/auth/users` | Get all users (Admin only) | Yes (JWT) |
| `POST` | `/auth/clerk` | Clerk webhook handler for external auth events | No (Webhook) |

#### Clerk Webhook Events

The `/auth/clerk` endpoint handles the following Clerk events:

- **`session.created`** — Logs in an existing user or auto-creates a new one
- **`session.removed`** / **`session.ended`** — Logs out the user
- **`user.created`** — Creates a new user from Clerk data
- **`user.updated`** — Updates user info from Clerk data
- **`user.deleted`** — Deletes the user

### Tuberculosis GeneXpert Endpoints

#### Facilities Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/tb/gx/facilities/registered_samples/` | Total samples registered by facility |
| `GET` | `/tb/gx/facilities/registered_samples_by_month/` | Registered samples by facility by month |
| `GET` | `/tb/gx/facilities/tested_samples/` | Total samples tested by facility |
| `GET` | `/tb/gx/facilities/tested_samples_by_month/` | Tested samples by facility by month |
| `GET` | `/tb/gx/facilities/tested_samples_disaggregated/` | Tested samples disaggregated by facility |
| `GET` | `/tb/gx/facilities/tested_samples_disaggregated_by_gender/` | Tested samples disaggregated by gender |
| `GET` | `/tb/gx/facilities/tested_samples_disaggregated_by_age/` | Tested samples disaggregated by age |
| `GET` | `/tb/gx/facilities/tested_samples_by_sample_types/` | Tested samples by sample types |
| `GET` | `/tb/gx/facilities/tested_samples_types_disaggregated_by_age/` | Sample types disaggregated by age |
| `GET` | `/tb/gx/facilities/tested_samples_disaggregated_by_drug_type/` | Tested samples by drug type |
| `GET` | `/tb/gx/facilities/tested_samples_disaggregated_by_drug_type_by_age/` | Tested samples by drug type and age |
| `GET` | `/tb/gx/facilities/rejected_samples/` | Rejected samples by facility |
| `GET` | `/tb/gx/facilities/rejected_samples_by_month/` | Rejected samples by facility by month |
| `GET` | `/tb/gx/facilities/rejected_samples_by_reason/` | Rejected samples by reason |
| `GET` | `/tb/gx/facilities/rejected_samples_by_reason_by_month/` | Rejected samples by reason by month |
| `GET` | `/tb/gx/facilities/trl_samples_by_days/` | Turnaround time in days |
| `GET` | `/tb/gx/facilities/trl_samples_by_days_by_month/` | Turnaround time in days by month |
| `GET` | `/tb/gx/facilities/trl_samples_avg_by_days/` | Average turnaround time in days |
| `GET` | `/tb/gx/facilities/trl_samples_avg_by_days_by_month/` | Average turnaround time by month |
| `GET` | `/tb/gx/facilities/trl_samples_by_days_tb/` | Turnaround time in days (TB-specific) |

#### Laboratory Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/tb/gx/laboratories/registered_samples/` | Registered samples by laboratory |
| `GET` | `/tb/gx/laboratories/tested_samples/` | Tested samples by laboratory |
| `GET` | `/tb/gx/laboratories/registered_samples_by_month/` | Registered samples by lab by month |
| `GET` | `/tb/gx/laboratories/tested_samples_by_month/` | Tested samples by lab by month |
| `GET` | `/tb/gx/laboratories/tested_samples_by_sample_types/` | Tested samples by sample types |
| `GET` | `/tb/gx/laboratories/tested_samples_by_sample_types_by_month/` | Sample types by month |
| `GET` | `/tb/gx/laboratories/rejected_samples/` | Rejected samples by laboratory |
| `GET` | `/tb/gx/laboratories/rejected_samples_by_month/` | Rejected samples by lab by month |
| `GET` | `/tb/gx/laboratories/rejected_samples_by_reason/` | Rejected samples by reason |
| `GET` | `/tb/gx/laboratories/rejected_samples_by_reason_by_month/` | Rejected by reason by month |
| `GET` | `/tb/gx/laboratories/tested_samples_by_drug_type/` | Tested samples by drug type |
| `GET` | `/tb/gx/laboratories/tested_samples_by_drug_type_by_month/` | Drug type by month |
| `GET` | `/tb/gx/laboratories/trl_samples_by_lab_in_days/` | Turnaround time in days |
| `GET` | `/tb/gx/laboratories/trl_samples_by_lab_in_days_by_month/` | Turnaround time by month |
| `GET` | `/tb/gx/laboratories/trl_samples_avg_by_days/` | Average turnaround time in days |
| `GET` | `/tb/gx/laboratories/trl_samples_avg_by_days_by_month/` | Average turnaround time by month |

#### Summary Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/tb/gx/summary/summary_header_component/` | Dashboard header component summary |
| `GET` | `/tb/gx/summary/positivity_by_month/` | Positivity rate by month |
| `GET` | `/tb/gx/summary/positivity_by_lab/` | Positivity rate by laboratory |
| `GET` | `/tb/gx/summary/positivity_by_lab_by_age/` | Positivity rate by lab by age |
| `GET` | `/tb/gx/summary/sample_types_by_month/` | Sample types by month by age |
| `GET` | `/tb/gx/summary/sample_types_by_facility_by_age/` | Sample types by facility by age |

#### Patient Endpoints

All patient endpoints require **Admin** role and support **pagination**.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/tb/gx/patients/by_name/` | Search patients by first name or surname (partial match) |
| `GET` | `/tb/gx/patients/by_facility/` | Get patients registered at a specific health facility |
| `GET` | `/tb/gx/patients/by_sample_type/` | Get patients filtered by sample type (`sputum`, `feces`, `urine`, `blood`) |
| `GET` | `/tb/gx/patients/by_result_type/` | Get patients filtered by result type (`detected`, `not_detected`, `indeterminate`, `error`, `invalid`) |

### HIV Viral Load Endpoints

#### Laboratory Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/hiv/vl/laboratories/registered_samples/` | Registered VL samples by laboratory |
| `GET` | `/hiv/vl/laboratories/registered_samples_by_month/` | Registered VL samples by month |
| `GET` | `/hiv/vl/laboratories/tested_samples/` | Tested VL samples by laboratory |
| `GET` | `/hiv/vl/laboratories/tested_samples_by_month/` | Tested VL samples by month |
| `GET` | `/hiv/vl/laboratories/tested_samples_by_gender/` | Tested VL samples by gender |
| `GET` | `/hiv/vl/laboratories/tested_samples_by_gender_by_lab/` | Tested VL samples by gender and laboratory |
| `GET` | `/hiv/vl/laboratories/tested_samples_by_age/` | Tested VL samples by age |
| `GET` | `/hiv/vl/laboratories/tested_samples_by_test_reason/` | Tested VL samples by test reason |
| `GET` | `/hiv/vl/laboratories/tested_samples_pregnant/` | Tested VL samples for pregnant clients |
| `GET` | `/hiv/vl/laboratories/tested_samples_breastfeeding/` | Tested VL samples for breastfeeding clients |
| `GET` | `/hiv/vl/laboratories/rejected_samples/` | Rejected VL samples by laboratory |
| `GET` | `/hiv/vl/laboratories/rejected_samples_by_month/` | Rejected VL samples by month |
| `GET` | `/hiv/vl/laboratories/tat_by_lab/` | Turnaround time by laboratory |
| `GET` | `/hiv/vl/laboratories/tat_by_month/` | Turnaround time by month |
| `GET` | `/hiv/vl/laboratories/suppression/` | Viral suppression indicators |

#### Facility Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/hiv/vl/facilities/registered_samples/` | Registered VL samples by facility |
| `GET` | `/hiv/vl/facilities/tested_samples_by_month/` | Tested VL samples by month |
| `GET` | `/hiv/vl/facilities/tested_samples_by_facility/` | Tested VL samples by facility |
| `GET` | `/hiv/vl/facilities/tested_samples_by_gender_by_month/` | Tested VL samples by gender and month |
| `GET` | `/hiv/vl/facilities/tested_samples_by_gender_by_facility/` | Tested VL samples by gender and facility |
| `GET` | `/hiv/vl/facilities/tested_samples_by_age_by_month/` | Tested VL samples by age and month |
| `GET` | `/hiv/vl/facilities/tested_samples_by_age_by_facility/` | Tested VL samples by age and facility |
| `GET` | `/hiv/vl/facilities/tested_samples_by_test_reason_by_month/` | Tested VL samples by test reason and month |
| `GET` | `/hiv/vl/facilities/tested_samples_by_test_reason_by_facility/` | Tested VL samples by test reason and facility |
| `GET` | `/hiv/vl/facilities/tested_samples_pregnant/` | Tested VL samples for pregnant clients |
| `GET` | `/hiv/vl/facilities/tested_samples_breastfeeding/` | Tested VL samples for breastfeeding clients |
| `GET` | `/hiv/vl/facilities/rejected_samples_by_month/` | Rejected VL samples by month |
| `GET` | `/hiv/vl/facilities/rejected_samples_by_facility/` | Rejected VL samples by facility |
| `GET` | `/hiv/vl/facilities/tat_by_month/` | Facility turnaround time by month |
| `GET` | `/hiv/vl/facilities/tat_by_facility/` | Facility turnaround time by facility |

#### Summary Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/hiv/vl/summary/header_indicators_by_month/` | Header indicators by month |
| `GET` | `/hiv/vl/summary/number_of_samples_by_month/` | Number of VL samples by month |
| `GET` | `/hiv/vl/summary/viral_suppression_by_month/` | Viral suppression by month |
| `GET` | `/hiv/vl/summary/tat_by_month/` | Turnaround time by month |
| `GET` | `/hiv/vl/summary/suppression_by_province_by_month/` | Viral suppression by province and month |
| `GET` | `/hiv/vl/summary/samples_history/` | Historical VL sample trend |

#### Patient Endpoints

All patient endpoints require **Admin** role and support **pagination**.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/hiv/vl/patients/by_name/` | Search VL patients by first name/surname |
| `GET` | `/hiv/vl/patients/by_facility/` | VL patients by health facility |
| `GET` | `/hiv/vl/patients/by_result_type/` | VL patients by result category |
| `GET` | `/hiv/vl/patients/by_test_reason/` | VL patients by test reason |

### HIV EID Endpoints

#### Laboratory Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/hiv/eid/laboratories/tested_samples_by_month/` | Tested EID samples by month |
| `GET` | `/hiv/eid/laboratories/registered_samples_by_month/` | Registered EID samples by month |
| `GET` | `/hiv/eid/laboratories/tested_samples/` | Tested EID samples |
| `GET` | `/hiv/eid/laboratories/tat/` | EID turnaround time summary |
| `GET` | `/hiv/eid/laboratories/tat_samples/` | EID turnaround time sample counts |
| `GET` | `/hiv/eid/laboratories/rejected_samples/` | Rejected EID samples |
| `GET` | `/hiv/eid/laboratories/rejected_samples_by_month/` | Rejected EID samples by month |
| `GET` | `/hiv/eid/laboratories/samples_by_equipment/` | EID samples by equipment |
| `GET` | `/hiv/eid/laboratories/samples_by_equipment_by_month/` | EID samples by equipment and month |
| `GET` | `/hiv/eid/laboratories/sample_routes/` | EID sample transport routes |
| `GET` | `/hiv/eid/laboratories/sample_routes_viewport/` | EID route viewport data |

#### Facility Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/hiv/eid/facilities/registered_samples/` | Registered EID samples by facility |
| `GET` | `/hiv/eid/facilities/registered_samples_by_month/` | Registered EID samples by month |
| `GET` | `/hiv/eid/facilities/tested_samples/` | Tested EID samples by facility |
| `GET` | `/hiv/eid/facilities/tested_samples_by_month/` | Tested EID samples by month |
| `GET` | `/hiv/eid/facilities/tested_samples_by_gender/` | Tested EID samples by gender |
| `GET` | `/hiv/eid/facilities/tested_samples_by_gender_by_month/` | Tested EID samples by gender and month |
| `GET` | `/hiv/eid/facilities/tat_avg_by_month/` | Average TAT by month |
| `GET` | `/hiv/eid/facilities/tat_avg/` | Average TAT by facility grouping |
| `GET` | `/hiv/eid/facilities/tat_days_by_month/` | TAT in days by month |
| `GET` | `/hiv/eid/facilities/tat_days/` | TAT in days by facility grouping |
| `GET` | `/hiv/eid/facilities/rejected_samples_by_month/` | Rejected EID samples by month |
| `GET` | `/hiv/eid/facilities/rejected_samples/` | Rejected EID samples by facility |
| `GET` | `/hiv/eid/facilities/key_indicators/` | Facility key indicators |
| `GET` | `/hiv/eid/facilities/tested_samples_by_age/` | Tested EID samples by age |

#### Summary Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/hiv/eid/summary/indicators/` | EID dashboard indicators |
| `GET` | `/hiv/eid/summary/tat/` | EID summary turnaround time |
| `GET` | `/hiv/eid/summary/tat_samples/` | EID summary TAT sample counts |
| `GET` | `/hiv/eid/summary/positivity/` | EID positivity summary |
| `GET` | `/hiv/eid/summary/number_of_samples/` | EID number of samples |
| `GET` | `/hiv/eid/summary/indicators_by_province/` | EID indicators by province |
| `GET` | `/hiv/eid/summary/samples_positivity/` | EID sample positivity trend |
| `GET` | `/hiv/eid/summary/rejected_samples_by_month/` | Rejected EID samples by month |
| `GET` | `/hiv/eid/summary/samples_by_equipment/` | EID samples by equipment |
| `GET` | `/hiv/eid/summary/samples_by_equipment_by_month/` | EID samples by equipment and month |

### Dictionary Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/dict/laboratories/` | Get all laboratories |
| `GET` | `/dict/laboratories/provinces/` | Get laboratories by province |
| `GET` | `/dict/laboratories/province/districts/` | Get laboratories by district |
| `GET` | `/dict/facilities/` | Get all facilities |
| `GET` | `/dict/facilities/provinces/` | Get facilities by province |
| `GET` | `/dict/facilities/province/districts/` | Get facilities by district |

## Common Parameters

The API accepts several common parameters across endpoints:

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `interval_dates` | string | Date range filter as `YYYY-MM-DD,YYYY-MM-DD` |
| `province` | string[] | Filter by province name (supports multiple values) |
| `district` | string[] | Filter by district name (supports multiple values) |
| `health_facility` | string | Filter by health facility name |
| `facility_type` | string | Type of facility (`province`, `district`, `health_facility`) |
| `gene_xpert_result_type` | string | GeneXpert result type filter |
| `type_of_laboratory` | string | Laboratory type |
| `laboratory` | string | Filter by laboratory name |
| `disaggregation` | string | Whether to include disaggregated data (`True`/`False`) |

### Patient-Specific Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `first_name` | string | Patient first name (partial match) |
| `surname` | string | Patient surname (partial match) |
| `sample_type` | string | Specimen type: `sputum`, `feces`, `urine`, `blood` |
| `result_type` | string | Result category: `detected`, `not_detected`, `indeterminate`, `error`, `invalid` |
| `test_reason` | string | VL patient test reason filter |

## Pagination

Patient endpoints support server-side pagination to handle large datasets efficiently. Pagination is applied at the SQL query level using `OFFSET`/`LIMIT` for optimal performance.

### Pagination Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | `1` | Page number (1-indexed) |
| `per_page` | integer | `50` | Number of records per page |

### Paginated Response Format

```json
{
    "status": "success",
    "page": 1,
    "per_page": 50,
    "total_count": 1234,
    "total_pages": 25,
    "data": [
        {
            "request_id": "REQ001",
            "first_name": "John",
            "last_name": "Doe",
            "health_facility": "CS Example",
            "final_result": "MTB Detected",
            ...
        }
    ]
}
```

### Example Requests

```
GET /tb/gx/patients/by_name/?first_name=Ana&page=1&per_page=20
GET /tb/gx/patients/by_facility/?health_facility=CS%20Mongue&page=2&per_page=50
GET /tb/gx/patients/by_sample_type/?sample_type=sputum&page=1&per_page=100
GET /tb/gx/patients/by_result_type/?result_type=detected&page=3&per_page=50
```

## Authentication

The API uses **JWT (JSON Web Tokens)** for authentication with two integration paths:

- Access tokens are configured to expire after **60 minutes**.

### Direct Login

```bash
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}'
```

The response includes a JWT token:

```json
{
    "message": "Login successful",
    "data": {
        "user_id": "...",
        "user_name": "admin",
        "first_name": "Admin",
        "last_name": "User",
        "email_address": "admin@example.com",
        "role": "Admin"
    },
    "token": "eyJhbGciOi...",
    "status": 200
}
```

### Using the Token

Include the token in the `Authorization` header for protected endpoints:

```bash
curl -H "Authorization: Bearer eyJhbGciOi..." \
  http://localhost:5000/tb/gx/patients/by_name/?first_name=Ana
```

### Clerk Integration

The API supports [Clerk](https://clerk.com/) as an external identity provider via webhook events at `/auth/clerk`. When a user authenticates through Clerk:

1. **New users** are automatically created in the local database
2. **Existing users** receive a new JWT access token
3. **User updates/deletions** from Clerk are synced to the local database
4. All events are logged to the `UserLogs` table

### Roles

- **Admin** — Full access to all endpoints, including patient data and user management
- **user** — Standard access (default role for Clerk-provisioned users)

## Getting Started

### Prerequisites

- Python 3.10+
- SQL Server (via `pyodbc`)
- Virtual environment (recommended)

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd OpenLDR_API
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .env
   # Windows
   .env\Scripts\activate
   # Linux/macOS
   source .env/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure the application:
   - Configuration is loaded from `configs/paths.py`.
   - **Windows**: values are read from `configs/configs.ini`.
   - **Linux**: values are read from environment variables.
   - In `app.py`, choose the active SQLAlchemy bind dictionary (currently `SQLALCHEMY_BINDS_CDR_OPENLDR_ORG_MZ`).
   - Ensure `FLASK_SECRET_KEY` (Linux) or `Flask.secret_key` (Windows), database credentials, and Clerk settings are configured.

5. Run the application:
   ```bash
   python app.py
   ```

6. Access the API documentation at: `http://localhost:5000/apidocs/`

## Deployment

### Production (Waitress + NSSM on Windows)

```bash
waitress-serve --host=127.0.0.1 --port=9001 app:app
```

To register as a Windows service using NSSM:

- **Path**: `<venv>\Scripts\python.exe`
- **Startup Directory**: `<project_root>\`
- **Arguments**: `-m waitress --host=127.0.0.1 --port=9001 app:app`
- **Service Name**: `OpenLDR_API`

### Docker

```bash
docker-compose up --build -d
```

## Environment Setup

### Windows configuration (`configs.ini`)

On Windows, `configs/paths.py` reads settings from `configs/configs.ini`.

Set at least:

- `Flask.secret_key`
- `Domains.local`, `Domains.cdr`, `Domains.cloud`, `Domains.tb`
- `Databases.database_user`, `Databases.database_password`
- `Databases.ViralLoadData`, `Databases.Dpi`, `Databases.HivAdvancedDisease`, `Databases.TBData`, `Databases.Dictionary`, `Databases.Users`
- `Schemas.cdr_schema`
- `Clerk.clerk_webhook_secret`, `Clerk.secret_key`, `Clerk.api_endpoint`, `Clerk.clerk_jwts_url`, `Clerk.clerk_issuer`, `Clerk.clerk_public_key`

For a named SQL Server instance, `Domains.cdr` can include the instance name, for example `disamoz.org.mz\SQLEXPRESS` or `CDR\SQLEXPRESS`.

### Linux configuration (environment variables)

On Linux, `configs/paths.py` reads environment variables.

Common variables:

- `FLASK_SECRET_KEY`
- `LOCAL_DOMAIN`, `CDR_DOMAIN`, `CLOUD_DOMAIN`, `TB_DASHBOARD_DOMAIN`
- `DB_USER`, `DB_PASSWORD`, `DB_VL_DATA`, `DB_DPI`, `DB_HIV_AD`, `DB_TB_DATA`, `DB_DICT`, `DB_USERS`
- `SCHEMA_CDR`
- `CLERK_WEBHOOK_SECRET_KEY`, `CLERK_SECRET_KEY`, `CLERK_API_URL`, `CLERK_JWTS_URL`, `CLERK_ISSUER`, `CLERK_PUBLIC_KEY`

For Coolify/Docker deployments that use the CDR SQL Server named instance, set `CDR_DOMAIN` to `disamoz.org.mz\SQLEXPRESS` when connecting from outside the server network, or `CDR\SQLEXPRESS` when the container can resolve the internal host. If SQLEXPRESS is configured with a fixed TCP port, use `host,port` instead, for example `disamoz.org.mz,14330`, and do not include `\SQLEXPRESS`.

### Database/driver notes

- SQL Server is required for normal operation.
- Connection strings use `ODBC Driver 18 for SQL Server` through an explicit `odbc_connect` string.
- ODBC encryption is enabled with `Encrypt=yes` and `TrustServerCertificate=yes`.
- MARS is disabled with `MARS_Connection=No`.
- The application name sent to SQL Server is `OpenLDR API`.
- ODBC pooling is not disabled by default. For diagnostics only, set `SQL_ODBC_POOLING=false` to add `Pooling=No` to the ODBC connection string.
- SQLAlchemy pooling stays enabled by default with `pool_pre_ping=True`, `pool_recycle=1800`, and a command timeout from `SQL_QUERY_TIMEOUT` (default `180`). For diagnostics only, set `SQLALCHEMY_DISABLE_POOLING=true` to use `NullPool`.
- Test the active CDR bind with `python scripts/check_mssql_connection.py`. The script prints `@@SERVERNAME`, `@@SERVICENAME`, and `DB_NAME()` without printing credentials.
- Confirm network access to the configured SQL Server hosts.

## Testing

The repository includes pytest tests in `tests/`.

```bash
# Unit-style utility tests
pytest tests/test_utils.py

# Full test suite
pytest tests -q

# Optional live integration checks (requires DB connectivity)
pytest tests/test_hiv_endpoints.py -s
```

## Troubleshooting

### Common Issues

#### Database Connection Errors
- **Issue**: `InterfaceError: ('IM002', '[IM002] [Microsoft][ODBC Driver Manager] Data source name not found'`
- **Solution**: Install ODBC Driver 18 for SQL Server and verify connection string format

#### JWT Token Issues
- **Issue**: `401 Unauthorized` despite valid login
- **Solution**: Check `SECRET_KEY` configuration and token expiration time

#### CORS Issues
- **Issue**: Browser blocks API requests from frontend
- **Solution**: Verify `Flask-CORS` configuration and allowed origins

#### Performance Issues
- **Issue**: Slow response times on large datasets
- **Solution**: Use pagination, optimize database queries, add indexes

### Debug Mode

Enable debug mode for detailed error information:

```python
# In app.py
app.run(debug=True)
```

### Logging

Check application logs for detailed error information:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

## Error Handling

The API uses standard HTTP status codes:

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Invalid Parameters |
| 401 | Unauthorized (missing or invalid token) |
| 403 | Forbidden (insufficient role permissions) |
| 404 | Resource Not Found |
| 500 | Internal Server Error |

### Error Response Format

```json
{
    "status": 500,
    "error": "Internal Server Error",
    "message": "Detailed error description"
}
```

### Patient Service Error Example

```json
{
    "status": "error",
    "code": 403,
    "message": "Forbidden - User with id abc123 and role user is not authorized to access this resource."
}
```
