"""
EID sample transport TAT, from ReportData.EIDTransportTATPerWeek (see hiv/transport_tat_service).
"""
from hiv import transport_tat_service as transport
from hiv.eid.models.report_data import EidTransportTatPerWeek


def transport_tat_by_location_service(req_args):
    return transport.tat_by_location(EidTransportTatPerWeek, req_args)


def transport_tat_by_week_service(req_args):
    return transport.tat_by_week(EidTransportTatPerWeek, req_args)
