"""
VL sample transport TAT, from ReportData.VLTransportTATPerWeek (see hiv/transport_tat_service).
"""
from hiv import transport_tat_service as transport
from hiv.vl.models.report_data import VlTransportTatPerWeek


def transport_tat_by_location_service(req_args):
    return transport.tat_by_location(VlTransportTatPerWeek, req_args)


def transport_tat_by_week_service(req_args):
    return transport.tat_by_week(VlTransportTatPerWeek, req_args)
