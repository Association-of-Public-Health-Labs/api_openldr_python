from sqlalchemy import func

from tb.cultura.models.tb_cultura_model import TBCultura
from tb.cultura.services.tb_cultura_services_common import (
    base_filters,
    common_response_fields,
    count_not_null,
    culture_result_columns,
    error_payload,
    get_request_context,
)
from utilities.utils import GET_COLUMN_NAME


def cultura_facility_metrics_service(req_args):
    try:
        ctx = get_request_context(req_args)
        facility_column = GET_COLUMN_NAME(
            ctx["disaggregation"],
            ctx["facility_type"],
            TBCultura,
            "facilities",
        )

        query = (
            TBCultura.query.with_entities(
                facility_column.label("Facility"),
                func.count().label("Registered_Samples"),
                count_not_null(TBCultura.AuthorisedDateTime, "Authorised_Samples"),
                *culture_result_columns(),
            )
            .filter(
                *base_filters(ctx, facility_flag="facilities"),
                facility_column.isnot(None),
            )
            .group_by(facility_column)
            .order_by(facility_column)
        )

        return [
            {
                "Facility": row.Facility,
                "Registered_Samples": row.Registered_Samples,
                "Authorised_Samples": row.Authorised_Samples,
                "Positive": row.Positive,
                "Negative": row.Negative,
                "Contaminated": row.Contaminated,
                "Pending": row.Pending,
                "Rejected": row.Rejected,
                **common_response_fields(ctx),
            }
            for row in query.all()
        ]
    except Exception as exc:
        return error_payload(exc)
