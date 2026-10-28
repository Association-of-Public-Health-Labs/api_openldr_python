"""Província/Distrito/US (facility) controllers for the HIV EID dashboard.

Each route reproduces a legacy openldr-api ClinicController route
(``/eid/clinic/*``); the Swagger description of each states its rule and ✱.
"""
from flask_restful import Resource

from hiv.eid.services.eid_services_facilities import (
    facility_registered_samples_service,
    facility_registered_samples_by_month_service,
    facility_tested_samples_service,
    facility_tested_samples_by_month_service,
    facility_tested_samples_by_gender_service,
    facility_tested_samples_by_gender_by_month_service,
    facility_tat_avg_by_month_service,
    facility_tat_avg_service,
    facility_tat_days_by_month_service,
    facility_tat_days_service,
    facility_rejected_samples_by_month_service,
    facility_rejected_samples_service,
    facility_key_indicators_service,
    facility_tested_samples_by_age_service,
)
from hiv.eid.controllers.eid_args import eid_parser
from utilities.controller_helpers import run_reporting_endpoint

_parser = eid_parser


class EidFacilityRegisteredSamples(Resource):
    def get(self):
        """
        EID registered samples per requesting province, district or facility

        Legacy clinic/samples_registered_province. RegisteredDateTime
        window. conventional / poc split on IsPoc alone ('No' / 'Yes'),
        as the legacy route did; total = every registered row. lab_type
        keeps one of the two. Level: province by default;
        disaggregation=true drills one level down (province -> district
        -> health facility; with no province, districts nationwide). To
        drill from a clicked bar, send facility_type = its level, its
        name in province / district, and disaggregation=true. Rows carry
        the name as requesting_facility. Rows with a NULL requesting
        province, district or facility name are left out (legacy); with
        no location given, a province stored as 'null' too. lab_code
        filters TestingFacilityCode. ✱5 the end day is included.
        ---
        tags:
            - HIV EID/Facilities
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
                description: "Rows: requesting_facility, conventional, poc, total"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, facility_registered_samples_service)


class EidFacilityRegisteredSamplesByMonth(Resource):
    def get(self):
        """
        EID monthly registered samples (Província/Distrito/US)

        Legacy clinic/samples_registered_month. By registration month
        (RegisteredDateTime window). conventional / poc split on IsPoc
        alone; total = every registered row. lab_type keeps one of the
        two. One row per month (year, month, month_name); facility_type
        picks the column the location filter applies to. Rows with a
        NULL requesting province, district or facility name are left out
        (legacy); with no location given, a province stored as 'null'
        too. lab_code filters TestingFacilityCode. ✱5 the end day is
        included.
        ---
        tags:
            - HIV EID/Facilities
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
                description: "Monthly rows: year, month, month_name, conventional, poc, total"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, facility_registered_samples_by_month_service)


class EidFacilityTestedSamples(Resource):
    def get(self):
        """
        EID tested samples per requesting province, district or facility

        Legacy clinic/samples_tested_province. AnalysisDateTime window;
        every analysed row (the legacy did not drop rejected rows).
        conventional / poc split on IsPoc alone; lab_type (Todos / PoC /
        Convencional) keeps one of the two. ✱7 positive and negative
        read FinalResult (new columns, the legacy route had none).
        Level: province by default; disaggregation=true drills one level
        down (province -> district -> health facility; with no province,
        districts nationwide). To drill from a clicked bar, send
        facility_type = its level, its name in province / district, and
        disaggregation=true. Rows carry the name as requesting_facility.
        Rows with a NULL requesting province, district or facility name
        are left out (legacy); with no location given, a province stored
        as 'null' too. lab_code filters TestingFacilityCode. ✱5 the end
        day is included.
        ---
        tags:
            - HIV EID/Facilities
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
                description: "Rows: requesting_facility, conventional, poc, total, positive, negative"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, facility_tested_samples_service)


class EidFacilityTestedSamplesByMonth(Resource):
    def get(self):
        """
        EID monthly tested samples (Província/Distrito/US)

        Legacy clinic/samples_tested_month. By analysis month
        (AnalysisDateTime window); as facilities/tested_samples/. ✱7
        positive and negative read FinalResult. One row per month (year,
        month, month_name); facility_type picks the column the location
        filter applies to. Rows with a NULL requesting province,
        district or facility name are left out (legacy); with no
        location given, a province stored as 'null' too. lab_code
        filters TestingFacilityCode. ✱5 the end day is included.
        ---
        tags:
            - HIV EID/Facilities
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
                description: "Monthly rows: year, month, month_name, conventional, poc, total, positive, negative"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, facility_tested_samples_by_month_service)


class EidFacilityTestedSamplesByGender(Resource):
    def get(self):
        """
        EID tested samples by sex and result per requesting province, district or facility

        Legacy clinic/samples_tested_gender_province. AnalysisDateTime
        window. Sex = HL7SexCode M / F. lab_type is the legacy category
        (all = Todos, poc = Poc, conventional = Convencional), on IsPoc.
        ✱7 results read FinalResult (the legacy read POC_Result /
        PCR_Result = 'Positivo' / 'Negativo', and its Todos category
        counted every POC_Result result whatever the sex). Level:
        province by default; disaggregation=true drills one level down
        (province -> district -> health facility; with no province,
        districts nationwide). To drill from a clicked bar, send
        facility_type = its level, its name in province / district, and
        disaggregation=true. Rows carry the name as requesting_facility.
        Rows with a NULL requesting province, district or facility name
        are left out (legacy); with no location given, a province stored
        as 'null' too. lab_code filters TestingFacilityCode. ✱5 the end
        day is included.
        ---
        tags:
            - HIV EID/Facilities
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
                description: "Rows: requesting_facility, male_positive, male_negative, female_positive, female_negative"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, facility_tested_samples_by_gender_service)


class EidFacilityTestedSamplesByGenderByMonth(Resource):
    def get(self):
        """
        EID monthly tested samples by sex and result (Província/Distrito/US)

        Legacy clinic/samples_tested_gender_month. By analysis month
        (AnalysisDateTime window); as
        facilities/tested_samples_by_gender/. ✱7 results read
        FinalResult. One row per month (year, month, month_name);
        facility_type picks the column the location filter applies to.
        Rows with a NULL requesting province, district or facility name
        are left out (legacy); with no location given, a province stored
        as 'null' too. lab_code filters TestingFacilityCode. ✱5 the end
        day is included.
        ---
        tags:
            - HIV EID/Facilities
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
                description: "Monthly rows: year, month, month_name, male_positive, male_negative, female_positive, female_negative"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, facility_tested_samples_by_gender_by_month_service)


class EidFacilityTatAvgByMonth(Resource):
    def get(self):
        """
        EID monthly average TAT of the six segments (Província/Distrito/US)

        Legacy clinic/samples_tat_avg_month. By analysis month
        (AnalysisDateTime window). Conventional only: IsPoc 'No'; hub
        dates before lab dates; TestingFacilityCode not 'PBC';
        registration -> analysis <= 30 days; hub registration -> lab
        reception >= 0 days; collection -> hub registration >= 0 days.
        Integer AVG(DATEDIFF(day)) per segment, an average of 0 reported
        as 1. One row per month (year, month, month_name); facility_type
        picks the column the location filter applies to. Rows with a
        NULL requesting province, district or facility name are left out
        (legacy); with no location given, a province stored as 'null'
        too. lab_code filters TestingFacilityCode. ✱5 the end day is
        included.
        ---
        tags:
            - HIV EID/Facilities
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
        return run_reporting_endpoint(_parser.parse_args, facility_tat_avg_by_month_service)


class EidFacilityTatAvg(Resource):
    def get(self):
        """
        EID average TAT of the six segments per requesting province, district or facility

        Legacy clinic/samples_tat_avg_province. AnalysisDateTime window;
        filters and averages as facilities/tat_avg_by_month/
        (conventional only). Level: province by default;
        disaggregation=true drills one level down (province -> district
        -> health facility; with no province, districts nationwide). To
        drill from a clicked bar, send facility_type = its level, its
        name in province / district, and disaggregation=true. Rows carry
        the name as requesting_facility. Rows with a NULL requesting
        province, district or facility name are left out (legacy); with
        no location given, a province stored as 'null' too. lab_code
        filters TestingFacilityCode. ✱5 the end day is included.
        ---
        tags:
            - HIV EID/Facilities
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: "Rows: requesting_facility + the six segment averages"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, facility_tat_avg_service)


class EidFacilityTatDaysByMonth(Resource):
    def get(self):
        """
        EID monthly TAT day brackets of one segment (Província/Distrito/US)

        Legacy clinic/samples_tat_days_month. By analysis month
        (AnalysisDateTime window). Conventional only: IsPoc 'No'; hub
        dates before lab dates; TestingFacilityCode not 'PBC';
        registration -> analysis <= 30 days. Counts of the category
        segment's days: < 7, 7-15, 16-21, > 21 and no dates (either date
        missing). One row per month (year, month, month_name);
        facility_type picks the column the location filter applies to.
        Rows with a NULL requesting province, district or facility name
        are left out (legacy); with no location given, a province stored
        as 'null' too. lab_code filters TestingFacilityCode. ✱5 the end
        day is included.
        ---
        tags:
            - HIV EID/Facilities
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/TATCategoryParameter'
            - $ref: '#/parameters/LabCodeParameter'
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
        return run_reporting_endpoint(_parser.parse_args, facility_tat_days_by_month_service)


class EidFacilityTatDays(Resource):
    def get(self):
        """
        EID TAT day brackets of one segment per requesting province, district or facility

        Legacy clinic/samples_tat_days_province. AnalysisDateTime
        window; filters and brackets as facilities/tat_days_by_month/
        (conventional only). Level: province by default;
        disaggregation=true drills one level down (province -> district
        -> health facility; with no province, districts nationwide). To
        drill from a clicked bar, send facility_type = its level, its
        name in province / district, and disaggregation=true. Rows carry
        the name as requesting_facility. Rows with a NULL requesting
        province, district or facility name are left out (legacy); with
        no location given, a province stored as 'null' too. lab_code
        filters TestingFacilityCode. ✱5 the end day is included.
        ---
        tags:
            - HIV EID/Facilities
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/TATCategoryParameter'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: "Rows: requesting_facility, category, lt_7, between_7_15, between_16_21, gt_21, no_dates"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, facility_tat_days_service)


class EidFacilityRejectedSamplesByMonth(Resource):
    def get(self):
        """
        EID monthly rejected samples by reason (Província/Distrito/US)

        Legacy clinic/samples_rejected_by_month. By analysis month
        (AnalysisDateTime window, as the legacy route), IsPoc 'No',
        LIMSRejectionCode not empty. 9 reasons; on this route REJOL
        counts as repeat_test and PRTLA as technical_problems (legacy);
        other = any other code. total = every rejected row. One row per
        month (year, month, month_name); facility_type picks the column
        the location filter applies to. Rows with a NULL requesting
        province, district or facility name are left out (legacy); with
        no location given, a province stored as 'null' too. lab_code
        filters TestingFacilityCode. ✱5 the end day is included.
        ---
        tags:
            - HIV EID/Facilities
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
        return run_reporting_endpoint(_parser.parse_args, facility_rejected_samples_by_month_service)


class EidFacilityRejectedSamples(Resource):
    def get(self):
        """
        EID rejected samples by reason per requesting province, district or facility

        Legacy clinic/samples_rejected_by_facility. AnalysisDateTime
        window (as the legacy route), IsPoc 'No', LIMSRejectionCode not
        empty. 9 reasons; on this route REJOL and PRTLA count as other
        (legacy). total = every rejected row. Level: province by
        default; disaggregation=true drills one level down (province ->
        district -> health facility; with no province, districts
        nationwide). To drill from a clicked bar, send facility_type =
        its level, its name in province / district, and
        disaggregation=true. Rows carry the name as requesting_facility.
        Rows with a NULL requesting province, district or facility name
        are left out (legacy); with no location given, a province stored
        as 'null' too. lab_code filters TestingFacilityCode. ✱5 the end
        day is included.
        ---
        tags:
            - HIV EID/Facilities
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: "Rows: requesting_facility + the 9 reasons + total"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, facility_rejected_samples_service)


class EidFacilityKeyIndicators(Resource):
    def get(self):
        """
        EID key indicators per requesting province, district or facility (Sumário map drill)

        Legacy clinic/conventional/key_indicators
        (lab_type=conventional) and clinic/poc/key_indicators
        (lab_type=poc). Rows analysed OR registered in the window.
        tested = AnalysisDateTime in the window; registered =
        RegisteredDateTime in the window; rejected = registered in the
        window and HL7ResultStatusCode 'X'; pending = registered in the
        window, no result and status not 'X'; positive = analysed in the
        window and positive. positivity = positive / tested (percent, 1
        decimal; 0 when nothing was tested). conventional / poc on IsPoc
        ('No' / 'Yes'); all = both. ✱1 each lab type gets its own data
        (the legacy province page showed the PoC rows on both tabs). ✱7
        pending and positive read FinalResult. Level: province by
        default; disaggregation=true drills one level down (province ->
        district -> health facility; with no province, districts
        nationwide). To drill from a clicked bar, send facility_type =
        its level, its name in province / district, and
        disaggregation=true. Rows carry the name as requesting_facility.
        Rows with a NULL requesting province, district or facility name
        are left out (legacy); with no location given, a province stored
        as 'null' too. lab_code filters TestingFacilityCode. ✱5 the end
        day is included.
        ---
        tags:
            - HIV EID/Facilities
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
                description: "Rows: requesting_facility, registered, tested, rejected, pending, positive, positivity"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, facility_key_indicators_service)


class EidFacilityTestedSamplesByAge(Resource):
    def get(self):
        """
        EID tested samples by age group (no dashboard card)

        Monthly rows per AgeInDays group (0-2, 2-9, 9-18, 18+ months),
        AnalysisDateTime window. Not used by any card (spec §4.3, follow-up);
        only moved to the rebuilt column names.
        ---
        tags:
            - HIV EID/Facilities
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/LabTypeParameter'
        responses:
            200:
                description: "Monthly rows: year, month, month_name, age_group, total"
            400:
                description: Invalid parameter (lab_type, category or interval_dates)
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return run_reporting_endpoint(_parser.parse_args, facility_tested_samples_by_age_service)
