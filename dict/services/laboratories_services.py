from dict.models.hf_lat_long_model import HFLatLong
from tb.gxpert.models.tb_gx_model import TBMaster
from utilities.utils import *


def get_all_laboratories():
    """
    Get all laboratories.

    :return: all laboratories in JSON format.
    """
    query = (
        TBMaster.query
        .with_entities(
            TBMaster.TestingFacilityName.label("LabName"),
            TBMaster.TestingFacilityCode.label("LabCode"),
        )
        .distinct()
        .filter(
            TBMaster.TestingFacilityCode.isnot(None),
            TBMaster.TestingFacilityName.isnot(None),
        )
    )


    data = query.all()

    data_json = [
        dict(
            LabCode=row.LabCode,
            LabName=row.LabName,
        )
        for row in data
    ]

    return data_json


def get_laboratories_by_province(req_args):
    """
    Get all laboratories by province.

    :param province: contains the province name as an argument.
    :return: all laboratories in the given province in JSON format.
    """
    province = req_args["province"]

    if province is not None:
        query = (
            TBMaster.query
            .with_entities(
                TBMaster.TestingFacilityCode.label("LabCode"),
                TBMaster.TestingFacilityName.label("LabName"),
                TBMaster.TestingProvinceName.label("ProvinceName"),
                TBMaster.TestingDistrictName.label("DistrictName"),
            ).distinct()
            .filter(
                TBMaster.TestingProvinceName.in_(province),
                TBMaster.TestingFacilityCode.isnot(None),
                TBMaster.TestingFacilityName.isnot(None),
            )
        )


        data = query.all()
        data_json = [
            dict(
                LabCode=row.LabCode,
                LabName=row.LabName,
                ProvinceName=row.ProvinceName,
                DistrictName=row.DistrictName
            )
            for row in data
        ]

        return data_json


def get_laboratories_by_district(req_args):
    """
    Get all laboratories by district.

    :param district: contains the district name as an argument.
    :return: all laboratories in the given district in JSON format.
    """
    district = req_args["district"]

    if district is not None:
        query = (
            TBMaster.query
            .with_entities(
                TBMaster.TestingFacilityName.label("LabName"),
                TBMaster.TestingProvinceName.label("ProvinceName"),
                TBMaster.TestingDistrictName.label("DistrictName"),
                TBMaster.TestingFacilityCode.label("LabCode"),
            ).distinct()
            .filter(
                TBMaster.TestingDistrictName.in_(district),
                TBMaster.TestingFacilityCode.isnot(None),
                TBMaster.TestingFacilityName.isnot(None),
            )
        )


        data = query.all()

        data_json = [
            dict(
                LabCode=row.LabCode,
                LabName=row.LabName,
                ProvinceName=row.ProvinceName,
                DistrictName=row.DistrictName,
            )
            for row in data
        ]

        return data_json