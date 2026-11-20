from dict.models.facilities_model import Facilities
from dict.models.hf_lat_long_model import HFLatLong
from utilities.utils import *


def get_all_facilities():
    """
    Get all facilities.

    :return: all facilities in JSON format.
    """

    query = (
        Facilities.query.outerjoin(
            HFLatLong, HFLatLong.FacilityCode == Facilities.FacilityCode
        )
        .with_entities(
            Facilities.FacilityCode.label("FacilityCode"),
            Facilities.FacilityNationalCode.label("FacilityNationalCode"),
            Facilities.FacilityType.label("FacilityType"),
            Facilities.Description.label("Description"),
            Facilities.ProvinceName.label("ProvinceName"),
            Facilities.DistrictName.label("DistrictName"),
            HFLatLong.Latt.label("Latitude"),
            HFLatLong.Long.label("Longitude"),
            Facilities.HFStatus.label("HFStatus"),
        )
        .filter(
            Facilities.HFStatus == 1, 
            Facilities.FacilityType == "H",
            Facilities.ProvinceName.isnot(None),
            Facilities.DistrictName.isnot(None),
            Facilities.Description.isnot(None),
        )
    )


    data = query.all()

    response = [
        dict(
            FacilityName=row.Description,
            FacilityCode=row.FacilityCode,
            FacilityType=row.FacilityType,
            FacilityNationalCode=row.FacilityNationalCode,
            ProvinceName=row.ProvinceName,
            DistrictName=row.DistrictName,
            HFStatus=row.HFStatus,
            Latitude=row.Latitude,
            Longitude=row.Longitude,
        )
        for row in data
    ]

    return response


def get_facilities_by_province(req_args):
    """
    Get all facilities by province.

    :param req_args: contains the province name as an argument.
    :return: all facilities in the given province in JSON format.
    """
    query = (
        Facilities.query.outerjoin(
            HFLatLong, HFLatLong.FacilityCode == Facilities.FacilityCode
        )
        .with_entities(
            Facilities.FacilityCode.label("FacilityCode"),
            Facilities.FacilityNationalCode.label("FacilityNationalCode"),
            Facilities.FacilityType.label("FacilityType"),
            Facilities.Description.label("Description"),
            Facilities.ProvinceName.label("ProvinceName"),
            Facilities.DistrictName.label("DistrictName"),
            HFLatLong.Latt.label("Latitude"),
            HFLatLong.Long.label("Longitude"),
            Facilities.HFStatus.label("HFStatus"),
        )
        .filter(
            Facilities.HFStatus == 1,
            Facilities.FacilityType == "H",
            Facilities.ProvinceName.in_(req_args["province"]),
            Facilities.ProvinceName.isnot(None),
            Facilities.DistrictName.isnot(None),
            Facilities.Description.isnot(None),
        )
    )


    data = query.all()

    # print(data)

    response = [
        dict(
            FacilityCode=row.FacilityCode,
            FacilityNationalCode=row.FacilityNationalCode,
            FacilityType=row.FacilityType,
            FacilityName=row.Description,
            ProvinceName=row.ProvinceName,
            DistrictName=row.DistrictName,
            Latitude=row.Latitude,
            Longitude=row.Longitude,
            HFStatus=row.HFStatus,
        )
        for row in data
    ]

    return response


def get_facilities_by_district(req_args):
    """
    Get all facilities by district.

    :param req_args: contains the province name and district name as arguments.
    :return: all facilities in the given district in JSON format.
    """
    if req_args["district"] is not None:
        query = (
            Facilities.query.outerjoin(
                HFLatLong, HFLatLong.FacilityCode == Facilities.FacilityCode
            )
            .with_entities(
                Facilities.FacilityCode.label("FacilityCode"),
                Facilities.FacilityNationalCode.label("FacilityNationalCode"),
                Facilities.FacilityType.label("FacilityType"),
                Facilities.Description.label("Description"),
                Facilities.ProvinceName.label("ProvinceName"),
                Facilities.DistrictName.label("DistrictName"),
                HFLatLong.Latt.label("Latitude"),
                HFLatLong.Long.label("Longitude"),
                Facilities.HFStatus.label("HFStatus"),
            )
            .filter(
                and_(
                    Facilities.HFStatus == 1,
                    Facilities.FacilityType == "H",
                ),
                Facilities.DistrictName.in_(req_args["district"]),
                Facilities.ProvinceName.isnot(None),
                Facilities.DistrictName.isnot(None),
                Facilities.Description.isnot(None),
            )
        )

        data = query.all()


        response = [
            dict(
                FacilityCode=row.FacilityCode,
                FacilityNationalCode=row.FacilityNationalCode,
                FacilityType=row.FacilityType,
                FacilityName=row.Description,
                ProvinceName=row.ProvinceName,
                DistrictName=row.DistrictName,
                Latitude=row.Latitude,
                Longitude=row.Longitude,
                HFStatus=row.HFStatus,
            )
            for row in data
        ]

        return response
