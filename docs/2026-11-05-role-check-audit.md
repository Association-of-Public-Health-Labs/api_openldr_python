# Role-check audit (Task A2)

Source: `git grep -nE 'user_role|require_admin|check_admin_access|_admin_only|\.role|"Role"'` outside tests.
"Patient rows" means the response carries identifiable rows (names, patient IDs).
With `PERMISSIONS_ENFORCED` on, every row below marked "patient_access_role" or "helper" gets its role
from the token's `patientData` permission (`"Admin"` with it, `"User"` without), never from the DB.

| Location | Check | Class | Behaviour with the flag on |
|---|---|---|---|
| `utilities/auth_helpers.py` `get_user_role`, `check_admin_access`, `require_admin` | role must be `"Admin"` | patient rows (helper) | `get_user_role` returns before any DB lookup |
| `utilities/service_helpers.py` `get_user_role` | role lookup | helper (no callers today) | same early return |
| `hiv/vl/services/vl_services_patients.py` `_admin_only` (4 routes) | `check_admin_access` | patient rows | patientData |
| `hiv/eid/services/eid_services_patients.py` `_admin_only` (3 routes) | `check_admin_access` | patient rows | patientData |
| `tb/gxpert/services/tb_gx_services_patients.py` `require_admin` (4 routes) | `require_admin` | patient rows | patientData |
| `hiv/vl/services/vl_services_facilities.py` `_facility_level_forbidden` (15 routes) | Admin when `facility_type=health_facility` | aggregate | returns `None`: open to any dashboard user |
| `tb/gxpert/services/tb_gx_services_facilities.py` (20 routes) | `facility_type == "health_facility"`: Admin gets `process_patients` rows, others 403 | patient rows | patient_access_role |
| `tb/gxpert/services/tb_gx_services_laboratories.py` (18 routes) | same pattern; rows come from `get_patients(lab=health_facility)` | patient rows | patient_access_role |
| `tb/gxpert/services/tb_gx_services_summary.py` (6 places) | `"Role"` response field only | other (no gate) | field shows Admin/User by patientData |
| `tb/cultura/services/tb_cultura_services_common.py` | `ctx["user_role"]` into the `"Role"` field only | other (no gate; no patient rows) | same |
| `"Role"` fields in TB facilities/laboratories aggregate branches | echo of the role | other | same |
| `auth/auth_service.py` (`_check_admin_permission`, `get_all_users_service`, `update_user_service`, `login`, ...) | DB `user.role != "Admin"` for user management | other (user admin, not lab data) | unchanged: still the DB role |
| `auth/auth_controller.py`, `auth/user_model.py` | `role` in token and response bodies | other | unchanged |

## Result

- No aggregate endpoint is still restricted by role, apart from the TB `facility_type=health_facility` branch, which returns
  patient rows (not an aggregate) and stays gated. VL's facility-level aggregates are opened per spec section 3.
- Every TB facilities/laboratories service has the gate; there is no `facility_type=health_facility` route in them without it.

## Note for Task A4 (`is_patient_request`)

`PROCESS_COMMON_PARAMS_FACILITY` (`utilities/utils.py`) sets `facility_type = "health_facility"` whenever a
`health_facility` param is present, even without `facility_type`. TB's patient dialog sends only that param, so the
rule "a /tb/ path with `facility_type=health_facility` or a `health_facility` param" is the right one, and a
`facility_type`-only check would miss it. `tests/test_patient_access.py` covers it
(`test_flag_on_tb_health_facility_param_alone_is_403_without_patient_data`).

Routes returning patient rows that the rule "`/patients/` in the path, or a /tb/ path with `facility_type=health_facility`
or a `health_facility` param" would miss: **none found.** Patient rows come from only three places:
`*/patients/*` routes (VL, EID, TB), and the TB facilities/laboratories services in their `health_facility` branch.
EID and VL have no patient-row route outside `/patients/`.

Over-matches, harmless: the rule also matches TB routes that take a `health_facility` filter but return aggregates
(summary, cultura), and TB `/tb/gx/facilities|laboratories/` routes called with `facility_type=health_facility` plus a
`health_facility` filter. Those are matched on purpose. VL and EID `health_facility` params must not match (aggregates).
