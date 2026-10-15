from flask_restful import Resource

from hiv.vl.services.vl_services_weekly import (
    weekly_report_service,
    weekly_report_national_service,
)
from hiv.vl.services.vl_services_laboratory import (
    registered_samples_service,
    registered_samples_by_month_service,
    tested_samples_service,
    tested_samples_by_month_service,
    tested_samples_by_gender_service,
    tested_samples_by_gender_by_lab_service,
    tested_samples_by_age_service,
    tested_samples_by_test_reason_service,
    tested_samples_pregnant_service,
    tested_samples_breastfeeding_service,
    rejected_samples_service,
    rejected_samples_by_month_service,
    tat_by_lab_service,
    tat_by_month_service,
    suppression_service,
)
from utilities.controller_helpers import (
    VL_FILTER_ARGS,
    build_common_parser,
    run_reporting_endpoint,
)


# Shared parser for all VL laboratory endpoints.
_parser = build_common_parser(extra_args=VL_FILTER_ARGS)


def _endpoint(service):
    """Local convenience wrapper around ``run_reporting_endpoint``."""
    return run_reporting_endpoint(_parser.parse_args, service)


class VlRegisteredSamples(Resource):
    def get(self):
        """
        Retrieve registered samples by laboratory
        ---
        tags:
            - HIV Viral Load/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Registered samples by laboratory
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return _endpoint(registered_samples_service)


class VlRegisteredSamplesByMonth(Resource):
    def get(self):
        """
        Retrieve registered samples by laboratory and month
        ---
        tags:
            - HIV Viral Load/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Registered samples by laboratory and month
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return _endpoint(registered_samples_by_month_service)


class VlTestedSamples(Resource):
    def get(self):
        """
        Retrieve tested samples by laboratory
        ---
        tags:
            - HIV Viral Load/Laboratories
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
                description: Tested samples by laboratory
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return _endpoint(tested_samples_service)


class VlTestedSamplesByMonth(Resource):
    def get(self):
        """
        Retrieve tested samples by month
        ---
        tags:
            - HIV Viral Load/Laboratories
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
                description: Tested samples by month
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return _endpoint(tested_samples_by_month_service)


class VlTestedSamplesByGender(Resource):
    def get(self):
        """
        Retrieve tested samples by gender
        ---
        tags:
            - HIV Viral Load/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Tested samples by gender
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return _endpoint(tested_samples_by_gender_service)


class VlTestedSamplesByGenderByLab(Resource):
    def get(self):
        """
        Retrieve tested samples by gender and laboratory
        ---
        tags:
            - HIV Viral Load/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Tested samples by gender and laboratory
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return _endpoint(tested_samples_by_gender_by_lab_service)


class VlTestedSamplesByAge(Resource):
    def get(self):
        """
        Retrieve tested samples by age group
        ---
        tags:
            - HIV Viral Load/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Tested samples by age group
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return _endpoint(tested_samples_by_age_service)


class VlTestedSamplesByTestReason(Resource):
    def get(self):
        """
        Retrieve tested samples by test reason
        ---
        tags:
            - HIV Viral Load/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Tested samples by test reason
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return _endpoint(tested_samples_by_test_reason_service)


class VlTestedSamplesPregnant(Resource):
    def get(self):
        """
        Retrieve tested samples for pregnant women
        ---
        tags:
            - HIV Viral Load/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Tested samples for pregnant women
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return _endpoint(tested_samples_pregnant_service)


class VlTestedSamplesBreastfeeding(Resource):
    def get(self):
        """
        Retrieve tested samples for breastfeeding women
        ---
        tags:
            - HIV Viral Load/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Tested samples for breastfeeding women
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return _endpoint(tested_samples_breastfeeding_service)


class VlRejectedSamples(Resource):
    def get(self):
        """
        Retrieve rejected samples by laboratory
        ---
        tags:
            - HIV Viral Load/Laboratories
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
                description: "Rejected samples per lab code (lab_code, testing_facility = dictionary LabName, total)"
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return _endpoint(rejected_samples_service)


class VlRejectedSamplesByMonth(Resource):
    def get(self):
        """
        Retrieve rejected samples by month
        ---
        tags:
            - HIV Viral Load/Laboratories
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
                description: Rejected samples by month
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return _endpoint(rejected_samples_by_month_service)


class VlTatByLab(Resource):
    def get(self):
        """
        Retrieve turnaround time by laboratory
        ---
        tags:
            - HIV Viral Load/Laboratories
        description: >
            Rows with a result and a non-negative collection-to-reception
            interval. ✱ No 90-day cap: the legacy API meant to apply one but
            never did.
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
                description: Turnaround time by laboratory
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return _endpoint(tat_by_lab_service)


class VlTatByMonth(Resource):
    def get(self):
        """
        Retrieve turnaround time by month
        ---
        tags:
            - HIV Viral Load/Laboratories
        description: >
            Rows with a result and a non-negative collection-to-reception
            interval. ✱ No 90-day cap: the legacy API meant to apply one but
            never did.
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
                description: Turnaround time by month
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return _endpoint(tat_by_month_service)


class VlSuppression(Resource):
    def get(self):
        """
        Retrieve suppression trend by month
        ---
        tags:
            - HIV Viral Load/Laboratories
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Suppression trend by month
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return _endpoint(suppression_service)


class VlWeeklyReport(Resource):
    def get(self):
        """
        Retrieve the weekly lab report (one row per lab and week)
        ---
        tags:
            - HIV Viral Load/Laboratories
        description: >
            Read from ReportData.Resume. Filters on the week's start date, both
            ends inclusive. Default window: the current Sunday-Saturday week.
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: lab_code, lab_name, week, start, end, backlogs, tests, registrations, rejections, capacity, tat
            400:
                description: Invalid interval_dates
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return _endpoint(weekly_report_service)


class VlWeeklyReportNational(Resource):
    def get(self):
        """
        Retrieve the national weekly report (one row per week)
        ---
        tags:
            - HIV Viral Load/Laboratories
        description: >
            Read from ReportData.Resume, summed over labs (tat is the mean of
            the lab TATs). Default window: the last 12 weeks.
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/LabCodeParameter'
        responses:
            200:
                description: week, start, end, backlogs, tests, registrations, rejections, capacity, tat
            400:
                description: Invalid interval_dates
            401:
                description: Missing or invalid JWT token
            500:
                description: An Error Occurred
        """
        return _endpoint(weekly_report_national_service)
