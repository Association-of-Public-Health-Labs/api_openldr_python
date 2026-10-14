from hiv.vl.controllers.vl_controller_laboratory import (
    VlWeeklyReport,
    VlWeeklyReportNational,
    VlRegisteredSamples,
    VlRegisteredSamplesByMonth,
    VlTestedSamples,
    VlTestedSamplesByMonth,
    VlTestedSamplesByGender,
    VlTestedSamplesByGenderByLab,
    VlTestedSamplesByAge,
    VlTestedSamplesByTestReason,
    VlTestedSamplesPregnant,
    VlTestedSamplesBreastfeeding,
    VlRejectedSamples,
    VlRejectedSamplesByMonth,
    VlTatByLab,
    VlTatByMonth,
    VlSuppression,
)
from hiv.vl.controllers.vl_controller_facility import (
    VlFacilityRegisteredSamples,
    VlFacilityTestedSamplesByMonth,
    VlFacilityTestedSamplesByFacility,
    VlFacilityTestedSamplesByGenderByMonth,
    VlFacilityTestedSamplesByGenderByFacility,
    VlFacilityTestedSamplesByAgeByMonth,
    VlFacilityTestedSamplesByAgeByFacility,
    VlFacilityTestedSamplesByTestReasonByMonth,
    VlFacilityTestedSamplesByTestReasonByFacility,
    VlFacilityTestedSamplesPregnant,
    VlFacilityTestedSamplesBreastfeeding,
    VlFacilityTestedSamplesPregnantByFacility,
    VlFacilityTestedSamplesBreastfeedingByFacility,
    VlFacilityRejectedSamplesByMonth,
    VlFacilityRejectedSamplesByFacility,
    VlFacilityTatByMonth,
    VlFacilityTatByFacility,
)
from hiv.vl.controllers.vl_controller_summary import (
    VlSummaryHeaderIndicatorsByMonth,
    VlSummaryNumberOfSamplesByMonth,
    VlSummaryViralSuppressionByMonth,
    VlSummaryTatByMonth,
    VlSummarySuppressionByProvinceByMonth,
    VlSummarySamplesHistoryByMonth,
    VlSummaryTatVsDisalinks,
)
from hiv.vl.controllers.vl_controller_patients import (
    VlPatientsByName,
    VlPatientsByFacility,
    VlPatientsByResultType,
    VlPatientsByTestReason,
)


def vl_routes(api):
    """
    Registers the routes for HIV Viral Load API endpoints.
    """
    # Laboratory Endpoints
    # Legacy: GET /samples
    api.add_resource(VlRegisteredSamples, "/hiv/vl/laboratories/registered_samples/")
    # Legacy: GET /lab_samples_tested_by_month (partial - registered)
    api.add_resource(VlRegisteredSamplesByMonth, "/hiv/vl/laboratories/registered_samples_by_month/")
    # Legacy: GET /lab_samples_tested_by_lab
    api.add_resource(VlTestedSamples, "/hiv/vl/laboratories/tested_samples/")
    # Legacy: GET /lab_samples_tested_by_month
    api.add_resource(VlTestedSamplesByMonth, "/hiv/vl/laboratories/tested_samples_by_month/")
    # Legacy: GET /lab_samples_tested_by_gender
    api.add_resource(VlTestedSamplesByGender, "/hiv/vl/laboratories/tested_samples_by_gender/")
    # Legacy: GET /lab_samples_tested_by_gender_and_labs
    api.add_resource(VlTestedSamplesByGenderByLab, "/hiv/vl/laboratories/tested_samples_by_gender_by_lab/")
    # Legacy: GET /lab_samples_tested_by_age
    api.add_resource(VlTestedSamplesByAge, "/hiv/vl/laboratories/tested_samples_by_age/")
    # Legacy: GET /lab_samples_by_test_reason
    api.add_resource(VlTestedSamplesByTestReason, "/hiv/vl/laboratories/tested_samples_by_test_reason/")
    # Legacy: GET /lab_samples_tested_pregnant
    api.add_resource(VlTestedSamplesPregnant, "/hiv/vl/laboratories/tested_samples_pregnant/")
    # Legacy: GET /lab_samples_tested_breastfeeding
    api.add_resource(VlTestedSamplesBreastfeeding, "/hiv/vl/laboratories/tested_samples_breastfeeding/")
    # Legacy: GET /lab_samples_rejected
    api.add_resource(VlRejectedSamples, "/hiv/vl/laboratories/rejected_samples/")
    # Legacy: GET /lab_samples_rejected_by_month
    api.add_resource(VlRejectedSamplesByMonth, "/hiv/vl/laboratories/rejected_samples_by_month/")
    # Legacy: GET /lab_tat
    api.add_resource(VlTatByLab, "/hiv/vl/laboratories/tat_by_lab/")
    # Legacy: GET /lab_tat_by_month
    api.add_resource(VlTatByMonth, "/hiv/vl/laboratories/tat_by_month/")
    # Legacy: GET /suppression
    api.add_resource(VlSuppression, "/hiv/vl/laboratories/suppression/")
    # Legacy: GET /lab_weekly_report
    api.add_resource(VlWeeklyReport, "/hiv/vl/laboratories/weekly_report/")
    # Legacy: GET /lab_weekly_report_national
    api.add_resource(VlWeeklyReportNational, "/hiv/vl/laboratories/weekly_report_national/")

    # Facility Endpoints
    # Legacy: GET /clinic_registered_samples_by_facility
    api.add_resource(VlFacilityRegisteredSamples, "/hiv/vl/facilities/registered_samples/")
    # Legacy: GET /clinic_samples_tested_by_month
    api.add_resource(VlFacilityTestedSamplesByMonth, "/hiv/vl/facilities/tested_samples_by_month/")
    # Legacy: GET /clinic_samples_tested_by_facility
    api.add_resource(VlFacilityTestedSamplesByFacility, "/hiv/vl/facilities/tested_samples_by_facility/")
    # Legacy: GET /clinic_samples_tested_by_gender
    api.add_resource(VlFacilityTestedSamplesByGenderByMonth, "/hiv/vl/facilities/tested_samples_by_gender_by_month/")
    # Legacy: GET /clinic_samples_tested_by_gender_and_facility
    api.add_resource(VlFacilityTestedSamplesByGenderByFacility, "/hiv/vl/facilities/tested_samples_by_gender_by_facility/")
    # Legacy: GET /clinic_samples_tested_by_age
    api.add_resource(VlFacilityTestedSamplesByAgeByMonth, "/hiv/vl/facilities/tested_samples_by_age_by_month/")
    # Legacy: GET /clinic_samples_tested_by_age_and_facility
    api.add_resource(VlFacilityTestedSamplesByAgeByFacility, "/hiv/vl/facilities/tested_samples_by_age_by_facility/")
    # Legacy: GET /clinic_samples_by_test_reason_by_month
    api.add_resource(VlFacilityTestedSamplesByTestReasonByMonth, "/hiv/vl/facilities/tested_samples_by_test_reason_by_month/")
    # Legacy: GET /clinic_samples_by_test_reason_by_facility
    api.add_resource(VlFacilityTestedSamplesByTestReasonByFacility, "/hiv/vl/facilities/tested_samples_by_test_reason_by_facility/")
    # Monthly series (no legacy route; Node's monthly versions were dead code)
    api.add_resource(VlFacilityTestedSamplesPregnant, "/hiv/vl/facilities/tested_samples_pregnant/")
    api.add_resource(VlFacilityTestedSamplesBreastfeeding, "/hiv/vl/facilities/tested_samples_breastfeeding/")
    # Legacy: GET /clinic_tests_by_pregnancy
    api.add_resource(VlFacilityTestedSamplesPregnantByFacility, "/hiv/vl/facilities/tested_samples_pregnant_by_facility/")
    # Legacy: GET /clinic_tests_by_breastfeeding
    api.add_resource(VlFacilityTestedSamplesBreastfeedingByFacility, "/hiv/vl/facilities/tested_samples_breastfeeding_by_facility/")
    # Legacy: GET /clinic_samples_rejected_by_month
    api.add_resource(VlFacilityRejectedSamplesByMonth, "/hiv/vl/facilities/rejected_samples_by_month/")
    # Legacy: GET /clinic_samples_rejected_by_facility
    api.add_resource(VlFacilityRejectedSamplesByFacility, "/hiv/vl/facilities/rejected_samples_by_facility/")
    # Legacy: GET /clinic_tat
    api.add_resource(VlFacilityTatByMonth, "/hiv/vl/facilities/tat_by_month/")
    # Legacy: GET /clinic_tat_by_facility
    api.add_resource(VlFacilityTatByFacility, "/hiv/vl/facilities/tat_by_facility/")

    # Summary/Dashboard Endpoints
    # No legacy equivalent (single-row header totals)
    api.add_resource(VlSummaryHeaderIndicatorsByMonth, "/hiv/vl/summary/header_indicators_by_month/")
    # Legacy: GET /dash_number_of_samples
    api.add_resource(VlSummaryNumberOfSamplesByMonth, "/hiv/vl/summary/number_of_samples_by_month/")
    # Legacy: GET /dash_viral_suppression
    api.add_resource(VlSummaryViralSuppressionByMonth, "/hiv/vl/summary/viral_suppression_by_month/")
    # Legacy: GET /dash_tat
    api.add_resource(VlSummaryTatByMonth, "/hiv/vl/summary/tat_by_month/")
    # Legacy: GET /dash_map
    api.add_resource(VlSummarySuppressionByProvinceByMonth, "/hiv/vl/summary/suppression_by_province_by_month/")
    # Legacy: GET /dash_indicators
    api.add_resource(VlSummarySamplesHistoryByMonth, "/hiv/vl/summary/samples_history/")
    # Legacy: GET /dash_tat_vs_disalinks
    api.add_resource(VlSummaryTatVsDisalinks, "/hiv/vl/summary/tat_vs_disalinks/")

    # Patients Endpoints
    api.add_resource(
        VlPatientsByName,
        "/hiv/vl/patients/by_name/",
    )

    api.add_resource(
        VlPatientsByFacility,
        "/hiv/vl/patients/by_facility/",
    )

    api.add_resource(
        VlPatientsByResultType,
        "/hiv/vl/patients/by_result_type/",
    )

    api.add_resource(
        VlPatientsByTestReason,
        "/hiv/vl/patients/by_test_reason/",
    )