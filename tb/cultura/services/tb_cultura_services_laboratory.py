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


def cultura_laboratory_metrics_service(req_args):
    try:
        ctx = get_request_context(req_args)
        lab_column = GET_COLUMN_NAME(
            ctx["disaggregation"],
            ctx["facility_type"],
            TBCultura,
            "laboratories",
        )

        query = (
            TBCultura.query.with_entities(
                lab_column.label("Laboratory"),
                func.count().label("Registered_Samples"),
                count_not_null(TBCultura.AnalysisDateTime, "Analysed_Samples"),
                count_not_null(TBCultura.AuthorisedDateTime, "Authorised_Samples"),
                *culture_result_columns(),
            )
            .filter(
                *base_filters(ctx, facility_flag="laboratories"),
                lab_column.isnot(None),
            )
            .group_by(lab_column)
            .order_by(lab_column)
        )

        return [
            {
                "Laboratory": row.Laboratory,
                "Registered_Samples": row.Registered_Samples,
                "Analysed_Samples": row.Analysed_Samples,
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
