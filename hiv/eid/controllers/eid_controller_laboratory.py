from flask_restful import Resource

from hiv.eid.services.eid_services_laboratory import (
    laboratory_labs_service,
    tested_samples_by_month_service,
    registered_samples_by_month_service,
    tested_samples_service,
    tat_service,
    tat_samples_service,
    rejected_samples_service,
    rejected_samples_by_month_service,
    samples_by_equipment_service,
    samples_by_equipment_by_month_service,
    sample_routes_service,
    sample_routes_viewport_service,
)
from hiv.eid.controllers.eid_args import EID_FILTER_ARGS, eid_parser
from utilities.controller_helpers import STR_ARG, build_common_parser, run_reporting_endpoint

_parser = eid_parser
# The map viewport (south,west,north,east) only applies to the viewport route.
_viewport_parser = build_common_parser(extra_args=EID_FILTER_ARGS + [("viewport", STR_ARG)])


class EidLaboratoryLabs(Resource):
    def get(self):
        """
        EID labs and PoC sites with their codes

        The distinct testing labs (TestingFacilityCode and TestingFacilityName,
        code not null) of the EID data, per lab type: conventional (IsPoc 'No',
        not a PIMA analyzer) and poc (IsPoc 'Yes' or a PIMA analyzer). A code
        seen under both types appears once per type. Sorted by name. Takes no
        parameters: no date window, no filter. Use the code as lab_code on the
        other laboratories routes, and to drill down from a lab bar.
        ---
        tags:
            - HIV EID/Laboratories
        responses:
            200:
                description: "Rows: code, name, lab_type ('conventional' or 'poc')"
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, laboratory_labs_service)


class EidTestedSamplesByMonth(Resource):
    def get(self):
        """
        EID monthly tested samples: total, positive, negative

        Legacy lab/all/samples_tested_by_month. By analysis month
        (AnalysisDateTime window); rejected rows (LIMSRejectionCode set) are
        left out. lab_type splits on IsPoc alone ('No' / 'Yes'), as the legacy
        route did. lab_code filters TestingFacilityCode. ✱5 the end day is
        included. ✱4/✱7 positive and negative read FinalResult (the legacy
        read PCR_Result, also for PoC).
        ---
        tags:
            - HIV EID/Laboratories
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
                description: "Monthly rows: year, month, month_name, total, positive, negative"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, tested_samples_by_month_service)


class EidRegisteredSamplesByMonth(Resource):
    def get(self):
        """
        EID monthly registered samples: total, conventional, poc

        Legacy lab/all/samples_registered_by_month. By registration month
        (RegisteredDateTime window). conventional / poc and lab_type split on
        IsPoc alone ('No' / 'Yes'), as the legacy route did. lab_code filters
        the receiving lab (ReceivingFacilityCode), the lab the legacy filtered
        by name. ✱5 the end day is included.
        ---
        tags:
            - HIV EID/Laboratories
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
        return run_reporting_endpoint(_parser.parse_args, registered_samples_by_month_service)


class EidTestedSamples(Resource):
    def get(self):
        """
        EID tested samples per laboratory, with drill to province, district and facility

        Legacy lab/conventional/samples_tested (lab_type=conventional) and
        lab/poc/samples_tested (lab_type=poc). AnalysisDateTime window;
        rejected rows (LIMSRejectionCode set) and rows with no testing lab are
        left out. Conventional = IsPoc 'No', not a PIMA analyzer and
        TestingFacilityCode not 'PBC'; PoC = IsPoc 'Yes' or a PIMA analyzer,
        with a testing lab code; all = either. Level: facility_type (lab by
        default, province, district, health_facility); disaggregation=true
        drills one level down (lab -> province -> district -> health_facility).
        To drill from a clicked bar, send facility_type = its level, its name
        or code in lab_code / province / district, and disaggregation=true.
        Rows carry testing_facility and testing_facility_code at the lab
        level (grouped by code + name: a name under two codes gives one row
        per code), requesting_facility at the others. lab_code filters TestingFacilityCode. ✱5 the end day is
        included. ✱4/✱7 positive and negative read FinalResult (the legacy PoC
        route read POC_Result, the conventional route PCR_Result).
        ---
        tags:
            - HIV EID/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - name: facility_type
              in: query
              type: string
              required: false
              enum: [lab, province, district, health_facility]
              description: Level of the rows (default lab = TestingFacilityName); with disaggregation, the level above them.
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/LabTypeParameter'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: "Rows: testing_facility (with testing_facility_code at the lab level) or requesting_facility, total, positive, negative"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, tested_samples_service)


class EidTat(Resource):
    def get(self):
        """
        EID TAT averages (6 segments, conventional) per laboratory, with drill

        Legacy lab/conventional/tat. AnalysisDateTime window. Integer
        AVG(DATEDIFF(day)) of each segment, an average of 0 reported as 1.
        Filters: not rejected (LIMSRejectionCode empty), IsPoc 'No' and not a
        PIMA analyzer, a testing lab name, TestingFacilityCode not PBC / PEM,
        hub dates before lab dates, hub registration to lab reception 0-90
        days, registration to analysis at most 30 days, collection to hub
        registration >= 0 days. Levels as laboratories/tested_samples/
        (facility_type, disaggregation). As in the legacy, district rows also
        carry province, and health facility rows province and district. Rows
        carry testing_facility and testing_facility_code at the lab level
        (grouped by code + name), requesting_facility at the others. lab_type does not apply. lab_code filters TestingFacilityCode.
        ✱5 the end day is included.
        ---
        tags:
            - HIV EID/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - name: facility_type
              in: query
              type: string
              required: false
              enum: [lab, province, district, health_facility]
              description: Level of the rows (default lab = TestingFacilityName); with disaggregation, the level above them.
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: "Rows: [province, district,] testing_facility (with testing_facility_code at the lab level) or requesting_facility, collection_hub_reception, hub_reception_hub_registration, hub_registration_lab_reception, lab_reception_lab_registration, lab_registration_analysis, analysis_validation"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, tat_service)


class EidTatSamples(Resource):
    def get(self):
        """
        EID TAT day brackets for one segment (category 0-5) per laboratory (conventional)

        Legacy lab/tat_samples. AnalysisDateTime window. Samples of segment
        `category` in <7, 7-15, 16-21, >21 days and without dates, per
        testing lab. Filters: IsPoc 'No', a testing lab name,
        TestingFacilityCode not PBC / UEM, hub dates before lab dates,
        registration to analysis at most 30 days, hub registration to lab
        reception >= 0 days (no 90-day limit), collection to hub registration
        >= 0 days. lab_code filters TestingFacilityCode. ✱5 the end day is
        included.
        ---
        tags:
            - HIV EID/Laboratories
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
                description: "Rows: testing_facility, testing_facility_code, category, lt_7, between_7_15, between_16_21, gt_21, no_dates"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, tat_samples_service)


class EidRejectedSamples(Resource):
    def get(self):
        """
        EID rejected samples by reason per receiving laboratory

        Legacy lab/rejected_samples. RegisteredDateTime window, IsPoc 'No',
        grouped by ReceivingFacilityName. Nine reasons from LIMSRejectionCode
        (REJOL and PRTLA count as other); total = every rejected row
        (rejection code or description), so a row rejected by description
        only is in total but in no reason. ✱2 lab_code now applies, on the
        receiving lab (ReceivingFacilityCode): the legacy card sent the wrong
        parameter, so its lab filter was ignored. ✱5 the end day is included.
        ---
        tags:
            - HIV EID/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: "Rows: receiving_facility, receiving_facility_code, repeat_test, insufficient_sample, request_without_sample, technical_problems, overlapping_blood, duplicate_registration, misidentified_sample, sample_over_30_days, other, total"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, rejected_samples_service)


class EidRejectedSamplesByMonth(Resource):
    def get(self):
        """
        EID monthly rejected samples by reason

        Legacy lab/rejected_samples_monthly. By registration month
        (RegisteredDateTime window), IsPoc 'No'. Reasons and total as
        laboratories/rejected_samples/. ✱2 lab_code now applies, on the
        receiving lab (ReceivingFacilityCode): the legacy card sent the wrong
        parameter, so its lab filter was ignored. ✱5 the end day is included.
        ---
        tags:
            - HIV EID/Laboratories
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
        return run_reporting_endpoint(_parser.parse_args, rejected_samples_by_month_service)


class EidSamplesByEquipment(Resource):
    def get(self):
        """
        EID tested samples by analyzer group per testing laboratory

        Legacy lab/samples_by_equipment. AnalysisDateTime window,
        HL7ResultStatusCode 'F', IsPoc 'No', TestingFacilityCode not 'PBC'.
        tested = every such row. lab_code filters TestingFacilityCode. ✱5 the
        end day is included. ✱8 analyzer groups add the codes the legacy
        missed (C680A to C6800, M200C to M2000, PNTHC to PANTHER, ALNTB to
        ALINITY), compared trimmed, so counts are expected to be higher than
        the legacy.
        ---
        tags:
            - HIV EID/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: "Rows: testing_facility, testing_facility_code, tested, CAPCTM, ALINITY, M2000, C6800, PANTHER, MPIMA, MANUAL"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, samples_by_equipment_service)


class EidSamplesByEquipmentByMonth(Resource):
    def get(self):
        """
        EID monthly tested samples by analyzer group

        Legacy lab/samples_by_equipment_monthly. By analysis month
        (AnalysisDateTime window), HL7ResultStatusCode 'F', IsPoc 'No', no PBC
        exclusion (as the legacy). tested = every such row. lab_code filters
        TestingFacilityCode. ✱5 the end day is included. ✱8 analyzer groups
        add the codes the legacy missed (C680A to C6800, M200C to M2000, PNTHC
        to PANTHER, ALNTB to ALINITY), compared trimmed, so counts are
        expected to be higher than the legacy.
        ---
        tags:
            - HIV EID/Laboratories
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
        return run_reporting_endpoint(_parser.parse_args, samples_by_equipment_by_month_service)


class EidSampleRoutes(Resource):
    def get(self):
        """
        Retrieve EID sample routes between facilities
        ---
        tags:
            - HIV EID/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/LabTypeParameter'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: EID sample routes
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, sample_routes_service)


class EidSampleRoutesViewport(Resource):
    def get(self):
        """
        Retrieve EID sample routes filtered by viewport
        ---
        tags:
            - HIV EID/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/LabTypeParameter'
            - $ref: '#/parameters/LabCodeParameter'
            - $ref: '#/parameters/ViewportParameter'
        responses:
            200:
                description: EID sample routes within viewport
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_viewport_parser.parse_args, sample_routes_viewport_service)
