from flask_restful import Resource

from hiv.vl.services.vl_services_facilities import (
    facility_registered_samples_service,
    facility_tested_samples_by_month_service,
    facility_tested_samples_by_facility_service,
    facility_tested_samples_by_month_by_gender_service,
    facility_tested_samples_by_gender_by_facility_service,
    facility_tested_samples_by_age_by_month_service,
    facility_tested_samples_by_age_by_facility_service,
    facility_tested_samples_by_test_reason_by_month_service,
    facility_tested_samples_by_test_reason_by_facility_service,
    facility_tested_samples_pregnant_service,
    facility_tested_samples_breastfeeding_service,
    facility_rejected_samples_by_month_service,
    facility_rejected_samples_by_facility_service,
    facility_tat_by_month_service,
    facility_tat_by_facility_service,
)
from utilities.controller_helpers import (
    VL_FILTER_ARGS,
    build_common_parser,
    run_reporting_endpoint,
)


# Shared parser for all VL facility endpoints.
_parser = build_common_parser(extra_args=VL_FILTER_ARGS)


def _endpoint(service):
    """Local convenience wrapper around ``run_reporting_endpoint``."""
    return run_reporting_endpoint(_parser.parse_args, service)


class VlFacilityRegisteredSamples(Resource):
    def get(self):
        """
        Retrieve registered samples by requesting facility
        ---
        tags:
            - HIV Viral Load/Facilities
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Registered samples by requesting facility
            401:
                description: Missing or invalid JWT token
            403:
                description: facility_type=health_facility requires an Admin
            500:
                description: An Error Occurred
        """
        return _endpoint(facility_registered_samples_service)


class VlFacilityTestedSamplesByMonth(Resource):
    def get(self):
        """
        Retrieve tested samples by month (facility)
        ---
        tags:
            - HIV Viral Load/Facilities
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Tested samples by month (facility)
            401:
                description: Missing or invalid JWT token
            403:
                description: facility_type=health_facility requires an Admin
            500:
                description: An Error Occurred
        """
        return _endpoint(facility_tested_samples_by_month_service)


class VlFacilityTestedSamplesByFacility(Resource):
    def get(self):
        """
        Retrieve tested samples grouped by requesting facility
        ---
        tags:
            - HIV Viral Load/Facilities
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Tested samples by requesting facility
            401:
                description: Missing or invalid JWT token
            403:
                description: facility_type=health_facility requires an Admin
            500:
                description: An Error Occurred
        """
        return _endpoint(facility_tested_samples_by_facility_service)


class VlFacilityTestedSamplesByGenderByMonth(Resource):
    def get(self):
        """
        Retrieve tested samples by gender (facility)
        ---
        tags:
            - HIV Viral Load/Facilities
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Tested samples by gender (facility)
            401:
                description: Missing or invalid JWT token
            403:
                description: facility_type=health_facility requires an Admin
            500:
                description: An Error Occurred
        """
        return _endpoint(facility_tested_samples_by_month_by_gender_service)


class VlFacilityTestedSamplesByGenderByFacility(Resource):
    def get(self):
        """
        Retrieve tested samples by gender and requesting facility
        ---
        tags:
            - HIV Viral Load/Facilities
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Tested samples by gender and requesting facility
            401:
                description: Missing or invalid JWT token
            403:
                description: facility_type=health_facility requires an Admin
            500:
                description: An Error Occurred
        """
        return _endpoint(facility_tested_samples_by_gender_by_facility_service)


class VlFacilityTestedSamplesByAgeByMonth(Resource):
    def get(self):
        """
        Retrieve tested samples by age group (facility)
        ---
        tags:
            - HIV Viral Load/Facilities
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/AgeRangeParameter'
        responses:
            200:
                description: Tested samples by age group (facility)
            401:
                description: Missing or invalid JWT token
            403:
                description: facility_type=health_facility requires an Admin
            500:
                description: An Error Occurred
        """
        return _endpoint(facility_tested_samples_by_age_by_month_service)


class VlFacilityTestedSamplesByAgeByFacility(Resource):
    def get(self):
        """
        Retrieve tested samples by age group and requesting facility
        ---
        tags:
            - HIV Viral Load/Facilities
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
            - $ref: '#/parameters/AgeRangeParameter'
        responses:
            200:
                description: Tested samples by age group and requesting facility
            401:
                description: Missing or invalid JWT token
            403:
                description: facility_type=health_facility requires an Admin
            500:
                description: An Error Occurred
        """
        return _endpoint(facility_tested_samples_by_age_by_facility_service)


class VlFacilityTestedSamplesByTestReasonByMonth(Resource):
    def get(self):
        """
        Retrieve tested samples by test reason (facility)
        ---
        tags:
            - HIV Viral Load/Facilities
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Tested samples by test reason (facility)
            401:
                description: Missing or invalid JWT token
            403:
                description: facility_type=health_facility requires an Admin
            500:
                description: An Error Occurred
        """
        return _endpoint(facility_tested_samples_by_test_reason_by_month_service)


class VlFacilityTestedSamplesByTestReasonByFacility(Resource):
    def get(self):
        """
        Retrieve tested samples by test reason (facility)
        ---
        tags:
            - HIV Viral Load/Facilities
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Tested samples by test reason (facility)
            401:
                description: Missing or invalid JWT token
            403:
                description: facility_type=health_facility requires an Admin
            500:
                description: An Error Occurred
        """
        return _endpoint(facility_tested_samples_by_test_reason_by_facility_service)


class VlFacilityTestedSamplesPregnant(Resource):
    def get(self):
        """
        Retrieve tested samples for pregnant women (facility)
        ---
        tags:
            - HIV Viral Load/Facilities
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Tested samples for pregnant women (facility)
            401:
                description: Missing or invalid JWT token
            403:
                description: facility_type=health_facility requires an Admin
            500:
                description: An Error Occurred
        """
        return _endpoint(facility_tested_samples_pregnant_service)


class VlFacilityTestedSamplesBreastfeeding(Resource):
    def get(self):
        """
        Retrieve tested samples for breastfeeding women (facility)
        ---
        tags:
            - HIV Viral Load/Facilities
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Tested samples for breastfeeding women (facility)
            401:
                description: Missing or invalid JWT token
            403:
                description: facility_type=health_facility requires an Admin
            500:
                description: An Error Occurred
        """
        return _endpoint(facility_tested_samples_breastfeeding_service)


class VlFacilityRejectedSamplesByMonth(Resource):
    def get(self):
        """
        Retrieve rejected samples by month (facility)
        ---
        tags:
            - HIV Viral Load/Facilities
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Rejected samples by month (facility)
            401:
                description: Missing or invalid JWT token
            403:
                description: facility_type=health_facility requires an Admin
            500:
                description: An Error Occurred
        """
        return _endpoint(facility_rejected_samples_by_month_service)


class VlFacilityRejectedSamplesByFacility(Resource):
    def get(self):
        """
        Retrieve rejected samples grouped by requesting facility
        ---
        tags:
            - HIV Viral Load/Facilities
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Rejected samples by requesting facility
            401:
                description: Missing or invalid JWT token
            403:
                description: facility_type=health_facility requires an Admin
            500:
                description: An Error Occurred
        """
        return _endpoint(facility_rejected_samples_by_facility_service)


class VlFacilityTatByMonth(Resource):
    def get(self):
        """
        Retrieve turnaround time by month (facility)
        ---
        tags:
            - HIV Viral Load/Facilities
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Turnaround time by month (facility)
            401:
                description: Missing or invalid JWT token
            403:
                description: facility_type=health_facility requires an Admin
            500:
                description: An Error Occurred
        """
        return _endpoint(facility_tat_by_month_service)


class VlFacilityTatByFacility(Resource):
    def get(self):
        """
        Retrieve turnaround time grouped by requesting facility
        ---
        tags:
            - HIV Viral Load/Facilities
        parameters:
            - $ref: '#/parameters/IntervalDates'
            - $ref: '#/parameters/ProvinceParameter'
            - $ref: '#/parameters/DistrictParameter'
            - $ref: '#/parameters/HealthFacilityParameter'
            - $ref: '#/parameters/FacilityType'
            - $ref: '#/parameters/DisaggregationParameter'
        responses:
            200:
                description: Turnaround time by requesting facility
            401:
                description: Missing or invalid JWT token
            403:
                description: facility_type=health_facility requires an Admin
            500:
                description: An Error Occurred
        """
        return _endpoint(facility_tat_by_facility_service)
