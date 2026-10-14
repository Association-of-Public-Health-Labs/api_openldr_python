# HIV Viral Load & EID Migration Design

> **Updated 2026-10-12:** VL parity work is specified in
> `openldr-monorepo/docs/superpowers/specs/2026-10-12-vl-dashboard-migration-design.md`
> (piece 1). VL now uses the `vl` bind (not `vlSMS`), has 45 routes
> (17 laboratory incl. 2 weekly, 17 facility, 7 summary, 4 patients), and is
> covered by SQL-compilation tests in `tests/hiv/test_vl_*_sql.py`.

**Date:** 2026-03-24
**Status:** Approved
**Branch:** `feature/hiv-vl-eid-migration`

## Summary

Migrate HIV Viral Load (VL) and Early Infant Diagnosis (EID) analytics endpoints from two legacy Node.js backends (`openldr-backend` and `openldr-api`) into the central Python/Flask API (`api_openldr_python`). The migration follows the TB GeneXpert module as the reference implementation pattern.

## Scope

### In Scope (Phase 1)
- **VL**: Laboratory (15), Facility (14), Summary/Dashboard (6) = **35 endpoints**
- **EID**: Laboratory (11), Facility (14), Summary/Dashboard (10) = **35 endpoints**
- Refactor existing VL module to match TB GeneXpert patterns
- Create new EID module from scratch
- Standardize query parameters across all modules
- TDD tests for all new and existing endpoints

### Out of Scope (Future Phases)
- VL Patient/Results endpoints (6 routes)
- VL Weekly Reports (10 routes)
- VL Monthly Reports (6 routes)
- VL Backlogs endpoints
- Advanced Diseases (CD4, CrAg, TB-LAM)

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Migration approach | Idiomatic rewrite using TB GeneXpert patterns | Consistency, leverages existing utility functions |
| EID test type split | Unified endpoints with `lab_type` parameter | Matches TB's `type_of_laboratory` pattern, fewer routes |
| EID module path | `/hiv/eid/` (not `/hiv/dpi/`) | International naming, matches legacy API paths |
| EID database bind | Reuse existing `dpi` bind | Already configured, points to correct database |
| Parameter naming | Standardize on TB GeneXpert convention | Consistency across entire API |
| Phase strategy | Core analytics first (Lab + Dashboard + Clinic) | Weekly/Monthly reports need separate DB tables |

## Architecture

### Module Structure

Both VL and EID modules follow identical MVC layering:

```
hiv/{vl,eid}/
├── __init__.py
├── routes.py                           # Route registrations with legacy mapping comments
├── models/
│   └── {model}.py                      # SQLAlchemy ORM model
├── controllers/
│   ├── {mod}_controller_laboratory.py  # Lab-level Resource classes
│   ├── {mod}_controller_facility.py    # Facility-level Resource classes
│   └── {mod}_controller_summary.py     # Dashboard/summary Resource classes
└── services/
    ├── {mod}_services_laboratory.py    # Lab query logic
    ├── {mod}_services_facilities.py    # Facility query logic
    └── {mod}_services_summary.py       # Summary query logic
```

### App Integration

Route registration in `app.py`:

```python
from hiv.vl.routes import vl_routes
from hiv.eid.routes import eid_routes

vl_routes(api)        # 35 endpoints (refactored from existing 1)
eid_routes(api)       # 35 endpoints (new)
tb_gxpert_routes(api) # existing
dict_routes(api)      # existing
authentication_routes(api) # existing
```

### Database Binds

| Module | Bind Key | Table | Existing? |
|--------|----------|-------|-----------|
| VL | `vl` | VlData | Yes (model exists) |
| EID | `dpi` | EIDMaster | Bind exists, model is new |

## Standardized Query Parameters

All VL and EID endpoints adopt the TB GeneXpert parameter convention:

| Parameter | Type | Description |
|-----------|------|-------------|
| `interval_dates` | JSON array | `["YYYY-MM-DD", "YYYY-MM-DD"]` |
| `province` | string(s) | Province name filter (multi-select) |
| `district` | string(s) | District name filter (multi-select) |
| `health_facility` | string | Specific facility name |
| `facility_type` | string | `"province"` \| `"district"` \| `"health_facility"` |
| `disaggregation` | string | `"True"` \| `"False"` |

### EID-Specific Parameters

| Parameter | Type | Values | Description |
|-----------|------|--------|-------------|
| `lab_type` | string | `"conventional"`, `"poc"`, `"all"` | Filter PCR vs POC testing |
| `category` | int | 0-5 | TAT segment index |
| `viewport` | JSON | `{lat: {low, high}, lng: {low, high}}` | Map viewport filter |

### EID TAT Category Segments

The `category` parameter maps to specific turnaround time segments in the EID specimen transport chain:

| Category | Segment | Date Fields |
|----------|---------|-------------|
| 0 | Collection → Hub Reception | `SpecimenDatetime` → `LIMSPreReg_ReceivedDateTime` |
| 1 | Hub Reception → Hub Registration | `LIMSPreReg_ReceivedDateTime` → `LIMSPreReg_RegistrationDateTime` |
| 2 | Hub Registration → Lab Reception | `LIMSPreReg_RegistrationDateTime` → `ReceivedDateTime` |
| 3 | Lab Reception → Lab Registration | `ReceivedDateTime` → `RegisteredDateTime` |
| 4 | Lab Registration → Analysis | `RegisteredDateTime` → `AnalysisDateTime` |
| 5 | Analysis → Validation | `AnalysisDateTime` → `AuthorisedDateTime` |

### EID Viewport Parameter

The `viewport` parameter is received as a JSON string query parameter and parsed server-side:

```
?viewport={"lat":{"low":-26.87,"high":-10.47},"lng":{"low":30.21,"high":40.84}}
```

Used to filter sample routes by geographic bounding box for map-based displays.

### VL-Specific Context

VL uses `ViralLoadResultCategory` ("Suppressed"/"Not Suppressed") as its key metric. The suppression logic filters on `AnalysisDateTime IS NOT NULL` to count only tested samples. Additional breakdowns:
- `ReasonForTest`: "Routine", "Suspected treatment failure" / "Suspeita de falha terapêutica", "Reason Not Specified" / "Não preenchido"
- `Pregnant`: "Yes"/"No" flag
- `BreastFeeding`: "Yes"/"No" flag

## VL Endpoint Mapping

### VL Laboratory Endpoints (15 routes)

| New Route | Legacy Route | Description |
|-----------|-------------|-------------|
| `/hiv/vl/laboratories/registered_samples/` | `/samples` | Registered samples by lab |
| `/hiv/vl/laboratories/registered_samples_by_month/` | `/lab_samples_tested_by_month` (partial) | Registered by lab by month |
| `/hiv/vl/laboratories/tested_samples/` | `/lab_samples_tested_by_lab` | Tested samples by lab |
| `/hiv/vl/laboratories/tested_samples_by_month/` | `/lab_samples_tested_by_month` | Tested by lab by month |
| `/hiv/vl/laboratories/tested_samples_by_gender/` | `/lab_samples_tested_by_gender` | By gender + suppression |
| `/hiv/vl/laboratories/tested_samples_by_gender_by_lab/` | `/lab_samples_tested_by_gender_and_labs` | Gender by lab |
| `/hiv/vl/laboratories/tested_samples_by_age/` | `/lab_samples_tested_by_age` | Age-stratified |
| `/hiv/vl/laboratories/tested_samples_by_test_reason/` | `/lab_samples_by_test_reason` | By reason for test |
| `/hiv/vl/laboratories/tested_samples_pregnant/` | `/lab_samples_tested_pregnant` | Pregnant patients |
| `/hiv/vl/laboratories/tested_samples_breastfeeding/` | `/lab_samples_tested_breastfeeding` | Breastfeeding patients |
| `/hiv/vl/laboratories/rejected_samples/` | `/lab_samples_rejected` | Rejected by lab |
| `/hiv/vl/laboratories/rejected_samples_by_month/` | `/lab_samples_rejected_by_month` | Rejections by month |
| `/hiv/vl/laboratories/tat_by_lab/` | `/lab_tat` | TAT by laboratory |
| `/hiv/vl/laboratories/tat_by_month/` | `/lab_tat_by_month` | TAT by month |
| `/hiv/vl/laboratories/suppression/` | `/suppression` | Viral suppression data |

### VL Facility Endpoints (14 routes)

| New Route | Legacy Route | Description |
|-----------|-------------|-------------|
| `/hiv/vl/facilities/registered_samples/` | `/clinic_registered_samples_by_facility` | Registered by facility |
| `/hiv/vl/facilities/tested_samples_by_month/` | `/clinic_samples_tested_by_month` | Tested by month |
| `/hiv/vl/facilities/tested_samples_by_facility/` | `/clinic_samples_tested_by_facility` | Tested by facility |
| `/hiv/vl/facilities/tested_samples_by_gender/` | `/clinic_samples_tested_by_gender` | By gender |
| `/hiv/vl/facilities/tested_samples_by_gender_by_facility/` | `/clinic_samples_tested_by_gender_and_facility` | Gender by facility |
| `/hiv/vl/facilities/tested_samples_by_age/` | `/clinic_samples_tested_by_age` | Age-stratified |
| `/hiv/vl/facilities/tested_samples_by_age_by_facility/` | `/clinic_samples_tested_by_age_and_facility` | Age + facility |
| `/hiv/vl/facilities/tested_samples_by_test_reason/` | `/clinic_samples_by_test_reason` | Test reasons |
| `/hiv/vl/facilities/tested_samples_pregnant/` | `/clinic_tests_by_pregnancy` | Pregnancy tests |
| `/hiv/vl/facilities/tested_samples_breastfeeding/` | `/clinic_tests_by_breastfeeding` | Breastfeeding tests |
| `/hiv/vl/facilities/rejected_samples_by_month/` | `/clinic_samples_rejected_by_month` | Monthly rejections |
| `/hiv/vl/facilities/rejected_samples_by_facility/` | `/clinic_samples_rejected_by_facility` | By facility |
| `/hiv/vl/facilities/tat_by_month/` | `/clinic_tat` | TAT by month |
| `/hiv/vl/facilities/tat_by_facility/` | `/clinic_tat_by_facility` | TAT by facility |

### VL Summary Endpoints (6 routes)

| New Route | Legacy Route | Description |
|-----------|-------------|-------------|
| `/hiv/vl/summary/header_indicators/` | `/dash_indicators` | Key indicators |
| `/hiv/vl/summary/number_of_samples/` | `/dash_number_of_samples` | Sample counts |
| `/hiv/vl/summary/viral_suppression/` | `/dash_viral_suppression` | Suppression trend |
| `/hiv/vl/summary/tat/` | `/dash_tat` | TAT summary |
| `/hiv/vl/summary/suppression_by_province/` | `/dash_map` | Provincial map data |
| `/hiv/vl/summary/samples_history/` | `/sampleshistory` | Samples history |

## EID Endpoint Mapping

### EID Laboratory Endpoints (11 routes)

| New Route | Legacy Route(s) | Description |
|-----------|----------------|-------------|
| `/hiv/eid/laboratories/tested_samples_by_month/` | `/lab/all/samples_tested_by_month`, `/lab/conventional/samples_tested_by_month`, `/lab/poc/samples_tested_by_month` | Tested by month (filtered by `lab_type`) |
| `/hiv/eid/laboratories/registered_samples_by_month/` | `/lab/all/samples_registered_by_month` | Registered by month |
| `/hiv/eid/laboratories/tested_samples/` | `/lab/conventional/samples_tested`, `/lab/poc/samples_tested` | Tested by lab (filtered by `lab_type`) |
| `/hiv/eid/laboratories/tat/` | `/lab/conventional/tat`, `/lab/poc/tat` | TAT by lab (filtered by `lab_type`) |
| `/hiv/eid/laboratories/tat_samples/` | `/lab/tat_samples` | TAT samples distribution |
| `/hiv/eid/laboratories/rejected_samples/` | `/lab/rejected_samples` | Rejected by lab |
| `/hiv/eid/laboratories/rejected_samples_by_month/` | `/lab/rejected_samples_monthly` | Rejected by month |
| `/hiv/eid/laboratories/samples_by_equipment/` | `/lab/samples_by_equipment` | By equipment type |
| `/hiv/eid/laboratories/samples_by_equipment_by_month/` | `/lab/samples_by_equipment_monthly` | Equipment by month |
| `/hiv/eid/laboratories/sample_routes/` | `/lab/sample_routes` | Sample transport routes |
| `/hiv/eid/laboratories/sample_routes_viewport/` | `/lab/sample_routes_viewport` | Routes by map viewport |

### EID Facility Endpoints (14 routes)

| New Route | Legacy Route | Description |
|-----------|-------------|-------------|
| `/hiv/eid/facilities/registered_samples/` | `/clinic/samples_registered_province` | Registered by facility |
| `/hiv/eid/facilities/registered_samples_by_month/` | `/clinic/samples_registered_month` | Registered by month |
| `/hiv/eid/facilities/tested_samples/` | `/clinic/samples_tested_province` | Tested by facility |
| `/hiv/eid/facilities/tested_samples_by_month/` | `/clinic/samples_tested_month` | Tested by month |
| `/hiv/eid/facilities/tested_samples_by_gender/` | `/clinic/samples_tested_gender_province` | Gender by facility |
| `/hiv/eid/facilities/tested_samples_by_gender_by_month/` | `/clinic/samples_tested_gender_month` | Gender by month |
| `/hiv/eid/facilities/tat_avg_by_month/` | `/clinic/samples_tat_avg_month` | Average TAT by month |
| `/hiv/eid/facilities/tat_avg/` | `/clinic/samples_tat_avg_province` | Average TAT by facility |
| `/hiv/eid/facilities/tat_days_by_month/` | `/clinic/samples_tat_days_month` | TAT day brackets by month |
| `/hiv/eid/facilities/tat_days/` | `/clinic/samples_tat_days_province` | TAT day brackets by facility |
| `/hiv/eid/facilities/rejected_samples_by_month/` | `/clinic/samples_rejected_by_month` | Rejections by month |
| `/hiv/eid/facilities/rejected_samples/` | `/clinic/samples_rejected_by_facility` | Rejections by facility |
| `/hiv/eid/facilities/key_indicators/` | `/clinic/conventional/key_indicators`, `/clinic/poc/key_indicators` | Key indicators (filtered by `lab_type`) |
| `/hiv/eid/facilities/tested_samples_by_age/` | (derived from clinic data) | Age-stratified by facility |

### EID Summary Endpoints (10 routes)

| New Route | Legacy Route(s) | Description |
|-----------|----------------|-------------|
| `/hiv/eid/summary/indicators/` | `/dash/pcr/indicators`, `/dash/poc/indicators` | Key indicators (filtered by `lab_type`) |
| `/hiv/eid/summary/tat/` | `/dash/pcr/tat` | TAT summary |
| `/hiv/eid/summary/tat_samples/` | `/dash/pcr/tat_samples` | TAT samples distribution |
| `/hiv/eid/summary/positivity/` | `/dash/pcr/positivity`, `/dash/poc/positivity` | Positivity rate (filtered by `lab_type`) |
| `/hiv/eid/summary/number_of_samples/` | `/dash/pcr/number_of_samples`, `/dash/poc/number_of_samples` | Sample counts (filtered by `lab_type`) |
| `/hiv/eid/summary/indicators_by_province/` | `/dash/indicators_by_province` | Provincial indicators |
| `/hiv/eid/summary/samples_positivity/` | `/dash/samples_positivity` | Positivity breakdown |
| `/hiv/eid/summary/rejected_samples_by_month/` | `/dash/rejected_samples_monthly` | Monthly rejections |
| `/hiv/eid/summary/samples_by_equipment/` | `/dash/samples_by_equipment` | Equipment summary |
| `/hiv/eid/summary/samples_by_equipment_by_month/` | `/dash/samples_by_equipment_monthly` | Equipment monthly |

## Data Models

### VlData (existing — refactor)

- File: `hiv/vl/models/vl.py`
- Bind: `vl`
- Table: `VlData`
- ~150 columns, already defined
- Key analytics columns: `ViralLoadResultCategory`, `HL7SexCode`, `AgeInYears`, `Pregnant`, `BreastFeeding`, `ReasonForTest`, facility/province/district names, datetime fields

### EIDMaster (new)

- File: `hiv/eid/models/eid_master_model.py`
- Bind: `dpi`
- Table: `EIDMaster`
- ~211 columns mapped from legacy TypeScript `IEIDMaster` interface
- Key analytics columns: `PCR_Result`, `POC_Result`, `IsPoc`, `HL7SexCode`, `AgeInDays`, rejection codes, facility chain, datetime fields, geographic coordinates, `LIMSAnalyzerName`

### Utility Functions

**Reuse from `utilities/utils.py`:**
- Date extraction: `YEAR()`, `MONTH()`, `QUARTER()`, `WEEK()`
- Counting: `TOTAL_ALL`, `TOTAL_NOT_NULL()`, `TOTAL_NULL()`, `TOTAL_IN()`
- TAT: `DATE_DIFF_AVG()`, `DATE_DIFF_MIN()`, `DATE_DIFF_MAX()`
- Gender: `GENDER_SUPPRESSION()`
- Lab type: `LAB_TYPE()`

**New utility functions:**
- `POSITIVITY(field, value)` — EID positive/negative counting
- `LAB_TYPE_EID(Model)` — Filter by `IsPoc` field
- `EQUIPMENT_COUNT(Model)` — Aggregate by equipment type (CAPCTM, ALINITY, M2000, C6800, PANTHER, MPIMA, MANUAL)

## Testing Strategy

### Structure

```
tests/
├── __init__.py
├── conftest.py                     # Shared fixtures
├── test_auth.py                    # Auth endpoint tests
├── test_dict.py                    # Dictionary endpoint tests
├── tb/
│   └── test_tb_gxpert.py           # TB GeneXpert tests
└── hiv/
    ├── test_vl_laboratory.py       # VL laboratory tests
    ├── test_vl_facility.py         # VL facility tests
    ├── test_vl_summary.py          # VL summary tests
    ├── test_eid_laboratory.py      # EID laboratory tests
    ├── test_eid_facility.py        # EID facility tests
    └── test_eid_summary.py         # EID summary tests
```

### Approach

- **Service-layer mocking**: Mock `db.session.query()` to return known data
- **Flask test client**: Test HTTP layer (status codes, JSON shape, parameter parsing)
- **JWT validation**: Verify 401 for unauthenticated requests

### Test Categories

1. **Route tests**: Endpoint exists, requires auth, returns correct status codes
2. **Controller tests**: Parameter parsing, correct service delegation, JSON response structure
3. **Service tests**: Query construction, filter logic, aggregation correctness

### Dependencies

```
pytest==8.1.1
pytest-cov==5.0.0
```

## Response Formats

All endpoints return JSON arrays of objects. Response schemas per category:

### VL Laboratory/Facility Response (tested samples, registered, by month)

```json
[
  {
    "year": 2025,
    "month": 1,
    "month_name": "January",
    "facility_name": "Lab Name / Facility Name",
    "total": 150,
    "total_not_null": 140,
    "total_null": 10,
    "suppressed": 120,
    "not_suppressed": 20,
    "male_suppressed": 60,
    "male_not_suppressed": 10,
    "female_suppressed": 60,
    "female_not_suppressed": 10
  }
]
```

### VL Test Reason Response

```json
[
  {
    "year": 2025,
    "month": 1,
    "month_name": "January",
    "total": 1000,
    "routine": 800,
    "treatment_failure": 150,
    "reason_not_specified": 50
  }
]
```

### VL/EID TAT Response

```json
[
  {
    "year": 2025,
    "month": 1,
    "month_name": "January",
    "facility_name": "Lab Name",
    "collection_reception": 2.5,
    "reception_registration": 1.2,
    "registration_analysis": 3.1,
    "analysis_validation": 0.8
  }
]
```

### EID Laboratory/Facility Response (tested samples)

```json
[
  {
    "year": 2025,
    "month": 1,
    "month_name": "January",
    "facility_name": "Lab Name",
    "total": 200,
    "tested": 180,
    "positive": 15,
    "negative": 165,
    "rejected": 10,
    "pending": 10,
    "female": 95,
    "male": 85
  }
]
```

### EID Equipment Response

```json
[
  {
    "facility_name": "Lab Name",
    "total": 500,
    "CAPCTM": 200,
    "ALINITY": 100,
    "M2000": 80,
    "C6800": 50,
    "PANTHER": 30,
    "MPIMA": 25,
    "MANUAL": 15
  }
]
```

### EID Sample Routes Response

```json
[
  {
    "requesting_facility": "Facility Name",
    "testing_facility": "Lab Name",
    "requesting_lat": "-25.96",
    "requesting_lng": "32.58",
    "testing_lat": "-25.97",
    "testing_lng": "32.59",
    "total": 50
  }
]
```

### VL/EID Summary Header Response

```json
{
  "registered": 10000,
  "tested": 9500,
  "suppressed": 8000,
  "not_suppressed": 1500,
  "rejected": 300,
  "pending": 200
}
```

Fields vary by endpoint — some endpoints include disaggregation columns (province/district/facility name) when `disaggregation=True`. The grouping column name matches the `facility_type` parameter value.

## Error Handling

Follow the TB GeneXpert pattern:

| HTTP Status | Condition | Response Body |
|-------------|-----------|---------------|
| 200 | Success | JSON array/object |
| 200 | No data found | Empty array `[]` |
| 401 | Missing/invalid JWT | `{"msg": "Missing Authorization Header"}` (Flask-JWT default) |
| 400 | Invalid parameters | `{"error": "Invalid parameter: <name>"}` |
| 500 | Database/server error | `{"error": "Internal server error"}` |

- All endpoints require `@jwt_required()` decorator
- Invalid date formats in `interval_dates` return 400
- Missing required parameters use sensible defaults (e.g., last 12 months, all provinces)
- Database connection failures are caught and return 500 with generic message (no SQL details exposed)

## Breaking Changes

This migration introduces the following breaking changes to the existing `api_openldr_python` VL module:

### Route Path Changes

| Before | After |
|--------|-------|
| `/hiv/vl/laboratory/registered_samples/` | `/hiv/vl/laboratories/registered_samples/` |

The path changes from singular `laboratory` to plural `laboratories` to match TB GeneXpert convention.

### Parameter Renames

| Before | After | Notes |
|--------|-------|-------|
| `provinces` | `province` | Multi-select still supported |
| `dates` | `interval_dates` | Same JSON array format |
| `filter_by` | `facility_type` | Same values: province/district/facility |

### File Renames

| Before | After |
|--------|-------|
| `hiv/vl/controllers/laboratory_controller.py` | `hiv/vl/controllers/vl_controller_laboratory.py` |
| `hiv/vl/controllers/facilities_controller.py` | `hiv/vl/controllers/vl_controller_facility.py` |
| `hiv/vl/controllers/summary_controller.py` | `hiv/vl/controllers/vl_controller_summary.py` |
| `hiv/vl/services/laboratory_services.py` | `hiv/vl/services/vl_services_laboratory.py` |
| `hiv/vl/services/facilities_services.py` | `hiv/vl/services/vl_services_facilities.py` |
| `hiv/vl/services/summary_services.py` | `hiv/vl/services/vl_services_summary.py` |

### Directory Removal

- `hiv/dpi/` — Empty placeholder directories removed, replaced by `hiv/eid/`

## Naming Conventions

All new code follows TB GeneXpert conventions:

| Element | Convention | Example |
|---------|-----------|---------|
| **Files** | `{mod}_controller_{category}.py` | `vl_controller_laboratory.py` |
| **Controller classes** | PascalCase, descriptive | `VlTestedSamplesByLab`, `EidTestedSamplesByMonth` |
| **Service functions** | snake_case | `get_tested_samples_by_lab()` |
| **Route paths** | lowercase, underscores, trailing slash | `/hiv/vl/laboratories/tested_samples/` |
| **Model classes** | PascalCase, table name | `VlData`, `EIDMaster` |
| **Utility functions** | UPPER_CASE for SQL helpers | `POSITIVITY()`, `LAB_TYPE_EID()` |

## Implementation Order

1. **VL Model** — Verify existing `VlData` model has all required columns
2. **VL Services** — Implement service functions (query logic) with TDD
3. **VL Controllers** — Implement Flask-RESTful Resource classes
4. **VL Routes** — Register all 35 endpoints with legacy mapping comments
5. **EID Model** — Create `EIDMaster` model from legacy TypeScript interface
6. **EID Services** — Implement service functions with TDD
7. **EID Controllers** — Implement Resource classes
8. **EID Routes** — Register all 35 endpoints
9. **App Integration** — Update `app.py`, cleanup old files/directories
10. **Swagger** — Update parameter definitions and endpoint documentation

## Cleanup

- Remove empty `hiv/dpi/` placeholder directories
- Refactor existing `hiv/vl/` single endpoint into new structure
- Rename existing VL files to match naming convention
- Standardize existing VL endpoint parameters to match TB convention
- Update `utilities/swagger.py` with VL and EID parameter definitions
