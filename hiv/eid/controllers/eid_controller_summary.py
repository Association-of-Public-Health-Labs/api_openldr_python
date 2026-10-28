from flask_restful import Resource
from hiv.eid.controllers.eid_args import eid_parser
from utilities.controller_helpers import run_reporting_endpoint
from hiv.eid.services.eid_services_summary import (
    summary_indicators_service,
    summary_tat_service,
    summary_tat_samples_service,
    summary_positivity_service,
    summary_number_of_samples_service,
    summary_indicators_by_province_service,
    summary_samples_positivity_service,
    summary_rejected_samples_by_month_service,
    summary_samples_by_equipment_service,
    summary_samples_by_equipment_by_month_service,
)


_parser = eid_parser


class EidSummaryIndicators(Resource):
    def get(self):
        """
        EID monthly indicators: registered, tested, rejected, pending

        Legacy dash/pcr/indicators + dash/poc/indicators. By registration month
        (RegisteredDateTime window). registered = every row; tested =
        AnalysisDateTime set; rejected = LIMSRejectionCode or LIMSRejectionDesc
        non-empty; pending = not rejected and FinalResult empty (or NDT /
        'Nível de detecção baixo'). KPI tiles are the sums of the months.
        ✱5 the end day is included. ✱6 lab_type uses the lab-type rule
        (conventional = IsPoc 'No' and not a PIMA analyzer; PoC = IsPoc 'Yes'
        or a PIMA analyzer) instead of RequestID digits. ✱7 pending reads
        FinalResult.
        ---
        tags:
            - HIV EID/Summary
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/LabTypeParameter'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: "Monthly rows: year, month, month_name, registered, tested, rejected, pending"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, summary_indicators_service)


class EidSummaryTat(Resource):
    def get(self):
        """
        EID monthly TAT averages (6 segments, conventional)

        Legacy dash/pcr/tat. By analysis month (AnalysisDateTime window).
        Integer AVG(DATEDIFF(day)) of each segment, IsPoc 'No', collection to
        lab reception >= 0 days, hub dates before lab dates, hub registration
        before lab reception, hub reception before lab registration. ✱5 the end
        day is included.
        ---
        tags:
            - HIV EID/Summary
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: "Monthly rows: year, month, month_name, collection_hub_reception, hub_reception_hub_registration, hub_registration_lab_reception, lab_reception_lab_registration, lab_registration_analysis, analysis_validation"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, summary_tat_service)


class EidSummaryTatSamples(Resource):
    def get(self):
        """
        EID monthly TAT day brackets for one segment (category 0-5, conventional)

        Legacy dash/pcr/tat_samples. By analysis month (AnalysisDateTime
        window). Samples of segment `category` in <7, 7-15, 16-21, >21 days and
        without dates; filters as summary/tat/ without 'hub reception before lab
        registration'. ✱5 the end day is included.
        ---
        tags:
            - HIV EID/Summary
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/LabCodeParameter'
            - $ref: '#/parameters/TATCategoryParameter'
        responses:
            200:
                description: "Monthly rows: year, month, month_name, category, lt_7, between_7_15, between_16_21, gt_21, no_dates"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, summary_tat_samples_service)


class EidSummaryPositivity(Resource):
    def get(self):
        """
        EID monthly positivity

        Legacy dash/samples_positivity. By analysis month (AnalysisDateTime
        window), HL7ResultStatusCode 'F'; tested = every such row.
        conventional_positive / poc_positive split by the lab-type rule; their sum can be less than
        positive, because rows with no analyzer code are in neither lab type
        (ruling R8).
        ✱3 positivity = positive / tested (percent, 1 decimal; 0 when nothing
        was tested), not conventional / total. ✱5 the end day is included.
        ✱7 results read FinalResult.
        ---
        tags:
            - HIV EID/Summary
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/LabTypeParameter'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: "Monthly rows: year, month, month_name, tested, positive, negative, indeterminate, conventional_positive, poc_positive, positivity"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, summary_positivity_service)


class EidSummaryNumberOfSamples(Resource):
    def get(self):
        """
        EID monthly sample counts (no dashboard card uses it)

        Legacy dash/pcr/number_of_samples + dash/poc/number_of_samples.
        AnalysisDateTime window, grouped by registration month (legacy).
        ✱5 the end day is included. ✱6 conventional / poc by the lab-type
        rule instead of RequestID digits.
        ---
        tags:
            - HIV EID/Summary
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/LabTypeParameter'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: "Monthly rows: year, month, month_name, total, conventional, poc"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, summary_number_of_samples_service)


class EidSummaryIndicatorsByProvince(Resource):
    def get(self):
        """
        EID indicators per requesting province (map)

        Legacy dash/indicators_by_province. RegisteredDateTime window,
        RequestingProvinceName not NULL. Tested, rejected and pending as in
        summary/indicators/; conventional = IsPoc 'No', poc = IsPoc 'Yes'
        (this legacy route's split); positivity = positive / tested (percent).
        ✱5 the end day is included. ✱7 positive and pending read FinalResult.
        ---
        tags:
            - HIV EID/Summary
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: "Rows: province, registered, tested, rejected, pending, conventional, poc, positive, positivity"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, summary_indicators_by_province_service)


class EidSummarySamplesPositivity(Resource):
    def get(self):
        """
        EID results by sex, one row (no dashboard card uses it)

        No legacy route. AnalysisDateTime window, HL7ResultStatusCode 'F',
        sex from HL7SexCode F / M. ✱5 the end day is included. ✱7 results read
        FinalResult.
        ---
        tags:
            - HIV EID/Summary
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/LabTypeParameter'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: "tested, positive, negative, indeterminate, female_positive, male_positive, female_negative, male_negative"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, summary_samples_positivity_service)


class EidSummaryRejectedSamplesByMonth(Resource):
    def get(self):
        """
        EID monthly rejected samples by reason (conventional)

        Legacy dash/rejected_samples_monthly. By registration month
        (RegisteredDateTime window), IsPoc 'No'. Nine reason buckets by
        LIMSRejectionCode (REJOL and PRTLA count as other); total = every
        rejected row (code or description). ✱5 the end day is included.
        ---
        tags:
            - HIV EID/Summary
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: "Monthly rows: year, month, month_name, repeat_test, insufficient_sample, request_without_sample, technical_problems, overlapping_blood, duplicate_registration, misidentified_sample, sample_over_30_days, other, total"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, summary_rejected_samples_by_month_service)


class EidSummarySamplesByEquipment(Resource):
    def get(self):
        """
        EID tested samples by analyzer group per testing lab (no dashboard card uses it)

        Legacy dash/samples_by_equipment. AnalysisDateTime window,
        HL7ResultStatusCode 'F', IsPoc 'No', no PBC exclusion. ✱5 the end day
        is included. ✱8 analyzer groups add the codes the legacy missed
        (C680A to C6800, M200C to M2000, PNTHC to PANTHER, ALNTB to ALINITY),
        compared trimmed, so counts are expected to be higher than the legacy.
        ---
        tags:
            - HIV EID/Summary
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: "Rows: testing_facility, tested, CAPCTM, ALINITY, M2000, C6800, PANTHER, MPIMA, MANUAL"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, summary_samples_by_equipment_service)


class EidSummarySamplesByEquipmentByMonth(Resource):
    def get(self):
        """
        EID monthly tested samples by analyzer group

        Legacy dash/samples_by_equipment_monthly. By analysis month
        (AnalysisDateTime window), HL7ResultStatusCode 'F', IsPoc 'No', no PBC
        exclusion. ✱5 the end day is included.
        ✱8 analyzer groups add the codes the legacy missed
        (C680A to C6800, M200C to M2000, PNTHC to PANTHER, ALNTB to ALINITY),
        compared trimmed, so counts are expected to be higher than the legacy.
        ---
        tags:
            - HIV EID/Summary
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: "Monthly rows: year, month, month_name, tested, CAPCTM, ALINITY, M2000, C6800, PANTHER, MPIMA, MANUAL"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, summary_samples_by_equipment_by_month_service)
