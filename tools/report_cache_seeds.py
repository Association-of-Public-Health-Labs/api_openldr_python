"""
Default reports the dashboards request on their first screen, recorded from the VL and TB apps
(2026-10-21); the EID ones are the default request of every card of the new EID dashboard (spec
2026-10-26 §4.3). The warm-up computes these even when the cache is empty (after a deploy); anything
else a visitor opened in the default period is in the cache already and gets recomputed with them.

Each seed is (path, window, params). Parameters are written as the dashboards send them: the cache
key is built from the request as it arrives, so "false" and "False" are different keys.
"""

from utilities.report_cache import MONTHS, YEAR

_VL = "/hiv/vl"
_TB = "/tb/gx"
_VL_FACILITY = {"facility_type": ["province"], "disaggregation": ["false"]}
_TB_FACILITY = {"disaggregation": ["False"]}

VL_SEEDS = [
    # Sumário
    (f"{_VL}/summary/number_of_samples_by_month/", YEAR, {}),
    (f"{_VL}/summary/viral_suppression_by_month/", YEAR, {}),
    (f"{_VL}/summary/tat_by_month/", YEAR, {}),
    (f"{_VL}/summary/suppression_by_province_by_month/", YEAR, {}),
    (f"{_VL}/summary/samples_history/", YEAR, {}),
    # Laboratório
    (f"{_VL}/laboratories/tested_samples/", YEAR, {}),
    (f"{_VL}/laboratories/tested_samples_by_month/", YEAR, {}),
    (f"{_VL}/laboratories/tat_by_lab/", YEAR, {}),
    (f"{_VL}/laboratories/tat_by_month/", YEAR, {}),
    (f"{_VL}/laboratories/rejected_samples/", YEAR, {}),
    (f"{_VL}/laboratories/rejected_samples_by_month/", YEAR, {}),
    # Província / Distrito / US
    (f"{_VL}/facilities/registered_samples/", YEAR, _VL_FACILITY),
    (f"{_VL}/facilities/tested_samples_by_facility/", YEAR, _VL_FACILITY),
    (f"{_VL}/facilities/tested_samples_by_gender_by_facility/", YEAR, _VL_FACILITY),
    (f"{_VL}/facilities/tested_samples_by_gender_by_month/", YEAR, _VL_FACILITY),
    (f"{_VL}/facilities/tat_by_month/", YEAR, _VL_FACILITY),
    (f"{_VL}/facilities/tat_by_facility/", YEAR, _VL_FACILITY),
    (f"{_VL}/facilities/tested_samples_by_age_by_facility/", YEAR, {**_VL_FACILITY, "age_range": ["15,49"]}),
    (f"{_VL}/facilities/tested_samples_pregnant_by_facility/", YEAR, _VL_FACILITY),
    (f"{_VL}/facilities/tested_samples_breastfeeding_by_facility/", YEAR, _VL_FACILITY),
    (f"{_VL}/facilities/tested_samples_by_test_reason_by_facility/", YEAR, _VL_FACILITY),
    (f"{_VL}/facilities/rejected_samples_by_month/", YEAR, _VL_FACILITY),
    (f"{_VL}/facilities/rejected_samples_by_facility/", YEAR, _VL_FACILITY),
]

# TB reports open on the Ultra tab; the XDR tab asks for the same reports with "XDR 10 Cores".
_TB_BY_TYPE = [
    # Sumário
    (f"{_TB}/summary/positivity_by_month/", YEAR, {}),
    (f"{_TB}/facilities/tested_samples/", YEAR, {}),
    (f"{_TB}/summary/positivity_by_lab_by_age/", YEAR, {}),
    (f"{_TB}/summary/sample_types_by_month/", YEAR, {}),
    (f"{_TB}/laboratories/rejected_samples_by_reason_by_month/", YEAR, {**_TB_FACILITY, "type_of_laboratory": ["Conventional"]}),
    # Província
    (f"{_TB}/facilities/registered_samples/", YEAR, _TB_FACILITY),
    (f"{_TB}/facilities/tested_samples/", YEAR, _TB_FACILITY),
    (f"{_TB}/facilities/tested_samples_disaggregated_by_gender/", YEAR, _TB_FACILITY),
    (f"{_TB}/facilities/trl_samples_by_days_tb/", YEAR, _TB_FACILITY),
    (f"{_TB}/facilities/tested_samples_disaggregated_by_drug_type/", YEAR, _TB_FACILITY),
    (f"{_TB}/facilities/rejected_samples/", YEAR, _TB_FACILITY),
    (f"{_TB}/facilities/rejected_samples_by_reason/", YEAR, _TB_FACILITY),
    (f"{_TB}/facilities/trl_samples_avg_by_days_by_month/", YEAR, _TB_FACILITY),
    (f"{_TB}/facilities/trl_samples_avg_by_days/", YEAR, _TB_FACILITY),
    # Laboratório (1st of the month, 11 months ago)
    (f"{_TB}/laboratories/registered_samples/", MONTHS, _TB_FACILITY),
    (f"{_TB}/laboratories/registered_samples_by_month/", MONTHS, _TB_FACILITY),
    (f"{_TB}/laboratories/rejected_samples/", MONTHS, _TB_FACILITY),
    (f"{_TB}/laboratories/rejected_samples_by_month/", MONTHS, _TB_FACILITY),
    (f"{_TB}/laboratories/rejected_samples_by_reason/", MONTHS, _TB_FACILITY),
    (f"{_TB}/laboratories/rejected_samples_by_reason_by_month/", MONTHS, {**_TB_FACILITY, "type_of_laboratory": ["Conventional"]}),
]

TB_SEEDS = [
    (f"{_TB}/summary/summary_header_component/", YEAR, {}),
    (f"{_TB}/summary/positivity_by_month/", YEAR, {}),
    (f"{_TB}/facilities/tested_samples_disaggregated_by_drug_type_by_age/", YEAR, {**_TB_FACILITY, "drug": ["Rifampicin"]}),
    *[
        (path, window, {**params, "genexpert_result_type": [result_type]})
        for result_type in ("Ultra 6 Cores", "XDR 10 Cores")
        for path, window, params in _TB_BY_TYPE
    ],
]


# The EID dashboard sends no lab_type and no category on its default requests (the API defaults:
# lab_type all, category 0), and facility routes as VL's. Map drills, the province page and patient
# routes carry a place or are never cached, so they are not seeds.
_EID = "/hiv/eid"
_EID_FACILITY = {"facility_type": ["province"], "disaggregation": ["false"]}

EID_SEEDS = [
    # Sumário
    (f"{_EID}/summary/indicators/", YEAR, {}),
    (f"{_EID}/summary/positivity/", YEAR, {}),
    (f"{_EID}/summary/indicators_by_province/", YEAR, {}),
    (f"{_EID}/summary/tat/", YEAR, {}),
    (f"{_EID}/summary/tat_samples/", YEAR, {}),
    (f"{_EID}/summary/rejected_samples_by_month/", YEAR, {}),
    (f"{_EID}/summary/samples_by_equipment_by_month/", YEAR, {}),
    # Laboratório
    (f"{_EID}/laboratories/tested_samples/", YEAR, {}),
    (f"{_EID}/laboratories/tested_samples_by_month/", YEAR, {}),
    (f"{_EID}/laboratories/registered_samples_by_month/", YEAR, {}),
    (f"{_EID}/laboratories/tat_samples/", YEAR, {}),
    (f"{_EID}/laboratories/tat/", YEAR, {}),
    (f"{_EID}/laboratories/samples_by_equipment_by_month/", YEAR, {}),
    (f"{_EID}/laboratories/samples_by_equipment/", YEAR, {}),
    (f"{_EID}/laboratories/rejected_samples_by_month/", YEAR, {}),
    (f"{_EID}/laboratories/rejected_samples/", YEAR, {}),
    # Província / Distrito / US
    (f"{_EID}/facilities/registered_samples/", YEAR, _EID_FACILITY),
    (f"{_EID}/facilities/registered_samples_by_month/", YEAR, _EID_FACILITY),
    (f"{_EID}/facilities/tested_samples/", YEAR, _EID_FACILITY),
    (f"{_EID}/facilities/tested_samples_by_month/", YEAR, _EID_FACILITY),
    (f"{_EID}/facilities/rejected_samples/", YEAR, _EID_FACILITY),
    (f"{_EID}/facilities/rejected_samples_by_month/", YEAR, _EID_FACILITY),
    (f"{_EID}/facilities/tested_samples_by_gender/", YEAR, _EID_FACILITY),
    (f"{_EID}/facilities/tested_samples_by_gender_by_month/", YEAR, _EID_FACILITY),
    (f"{_EID}/facilities/tat_avg/", YEAR, _EID_FACILITY),
    (f"{_EID}/facilities/tat_avg_by_month/", YEAR, _EID_FACILITY),
    (f"{_EID}/facilities/tat_days/", YEAR, _EID_FACILITY),
    (f"{_EID}/facilities/tat_days_by_month/", YEAR, _EID_FACILITY),
]


def seed_keys():
    """The seeds as cache keys (same shape as ``report_cache.cache_key``)."""
    return [
        {"path": path, "window": window, "params": dict(sorted(params.items()))}
        for path, window, params in VL_SEEDS + TB_SEEDS + EID_SEEDS
    ]
