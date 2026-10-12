from sqlalchemy import and_, case, func, text

from tb.cultura.models.tb_cultura_model import TBCultura
from tb.cultura.services.tb_cultura_services_common import (
    base_filters,
    common_response_fields,
    count_if,
    count_not_null,
    culture_result_columns,
    error_payload,
    get_request_context,
    tat_days,
)
from utilities.utils import DATE_PART, MONTH, YEAR


def cultura_summary_indicators_service(req_args):
    try:
        ctx = get_request_context(req_args)
        query = TBCultura.query.with_entities(
            func.count().label("Registered_Samples"),
            count_not_null(TBCultura.ReceivedDateTime, "Received_Samples"),
            count_not_null(TBCultura.AnalysisDateTime, "Analysed_Samples"),
            count_not_null(TBCultura.AuthorisedDateTime, "Authorised_Samples"),
            *culture_result_columns(),
            func.avg(
                case(
                    (
                        and_(
                            TBCultura.SpecimenDateTime.isnot(None),
                            TBCultura.AuthorisedDateTime.isnot(None),
                        ),
                        tat_days(),
                    ),
                    else_=None,
                )
            ).label("Avg_TAT_Days"),
        ).filter(*base_filters(ctx))

        row = query.one()
        return [
            {
                "Registered_Samples": row.Registered_Samples,
                "Received_Samples": row.Received_Samples,
                "Analysed_Samples": row.Analysed_Samples,
                "Authorised_Samples": row.Authorised_Samples,
                "Positive": row.Positive,
                "Negative": row.Negative,
                "Contaminated": row.Contaminated,
                "Pending": row.Pending,
                "Rejected": row.Rejected,
                "Avg_TAT_Days": row.Avg_TAT_Days,
                **common_response_fields(ctx),
            }
        ]
    except Exception as exc:
        return error_payload(exc)


def cultura_results_by_month_service(req_args):
    try:
        ctx = get_request_context(req_args)
        query = (
            TBCultura.query.with_entities(
                YEAR(TBCultura.RegisteredDateTime).label("Year"),
                MONTH(TBCultura.RegisteredDateTime).label("Month"),
                DATE_PART("month", TBCultura.RegisteredDateTime).label("Month_Name"),
                func.count().label("Registered_Samples"),
                count_not_null(TBCultura.AuthorisedDateTime, "Authorised_Samples"),
                *culture_result_columns(),
            )
            .filter(*base_filters(ctx), TBCultura.RegisteredDateTime.isnot(None))
            .group_by(
                YEAR(TBCultura.RegisteredDateTime),
                MONTH(TBCultura.RegisteredDateTime),
                DATE_PART("month", TBCultura.RegisteredDateTime),
            )
            .order_by(
                YEAR(TBCultura.RegisteredDateTime),
                MONTH(TBCultura.RegisteredDateTime),
            )
        )

        return [
            {
                "Year": row.Year,
                "Month": row.Month,
                "Month_Name": row.Month_Name,
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


def cultura_tat_and_backlog_service(req_args):
    try:
        ctx = get_request_context(req_args)
        age_in_backlog = func.datediff(
            text("day"),
            TBCultura.RegisteredDateTime,
            func.getdate(),
        )

        query = TBCultura.query.with_entities(
            func.count().label("Total"),
            count_if(TBCultura.AuthorisedDateTime.is_(None), "Pending"),
            count_if(
                and_(
                    TBCultura.AuthorisedDateTime.is_(None),
                    age_in_backlog.between(0, 7),
                ),
                "Pending_0_7_Days",
            ),
            count_if(
                and_(
                    TBCultura.AuthorisedDateTime.is_(None),
                    age_in_backlog.between(8, 30),
                ),
                "Pending_8_30_Days",
            ),
            count_if(
                and_(
                    TBCultura.AuthorisedDateTime.is_(None),
                    age_in_backlog > 30,
                ),
                "Pending_Over_30_Days",
            ),
            func.avg(
                case(
                    (
                        and_(
                            TBCultura.SpecimenDateTime.isnot(None),
                            TBCultura.AuthorisedDateTime.isnot(None),
                        ),
                        tat_days(),
                    ),
                    else_=None,
                )
            ).label("Avg_TAT_Days"),
        ).filter(*base_filters(ctx))

        row = query.one()
        return [
            {
                "Total": row.Total,
                "Pending": row.Pending,
                "Pending_0_7_Days": row.Pending_0_7_Days,
                "Pending_8_30_Days": row.Pending_8_30_Days,
                "Pending_Over_30_Days": row.Pending_Over_30_Days,
                "Avg_TAT_Days": row.Avg_TAT_Days,
                **common_response_fields(ctx),
            }
        ]
    except Exception as exc:
        return error_payload(exc)


def cultura_diagnostic_cascade_service(req_args):
    try:
        ctx = get_request_context(req_args)
        query = TBCultura.query.with_entities(
            func.count().label("Registered_Samples"),
            count_not_null(TBCultura.ReceivedDateTime, "Received_Samples"),
            count_if(
                (
                    TBCultura.LiquidCultureResult.isnot(None)
                    | TBCultura.SolidCultureResult.isnot(None)
                    | TBCultura.FinalMGITCultureResult.isnot(None)
                    | TBCultura.FinalLJCultureResult.isnot(None)
                ),
                "Culture_Performed",
            ),
            count_not_null(TBCultura.TBIDResult, "TBID_Performed"),
            count_if(
                (
                    TBCultura.LPAIsoniazidResult.isnot(None)
                    | TBCultura.LPARifampicinResult.isnot(None)
                ),
                "LPA_First_Line_Performed",
            ),
            count_if(
                (
                    TBCultura.LPA2FluoroquinoloneResult.isnot(None)
                    | TBCultura.LPA2KACResult.isnot(None)
                    | TBCultura.LPA2KACVResult.isnot(None)
                    | TBCultura.LPA2KCVResult.isnot(None)
                ),
                "LPA_Second_Line_Performed",
            ),
            count_if(
                (
                    TBCultura.TSAIsoniazidResult.isnot(None)
                    | TBCultura.TSARifampicinResult.isnot(None)
                    | TBCultura.TSAEthambutolResult.isnot(None)
                    | TBCultura.TSAPyrazinamideResult.isnot(None)
                ),
                "TSA_First_Line_Performed",
            ),
            count_if(
                (
                    TBCultura.TSA2AmikacinResult.isnot(None)
                    | TBCultura.TSA2LevofloxacinResult.isnot(None)
                    | TBCultura.TSA2MoxifloxacinResult.isnot(None)
                    | TBCultura.TSA2BedaquilineResult.isnot(None)
                ),
                "TSA_Second_Line_Performed",
            ),
        ).filter(*base_filters(ctx))

        row = query.one()
        return [
            {
                "Registered_Samples": row.Registered_Samples,
                "Received_Samples": row.Received_Samples,
                "Culture_Performed": row.Culture_Performed,
                "TBID_Performed": row.TBID_Performed,
                "LPA_First_Line_Performed": row.LPA_First_Line_Performed,
                "LPA_Second_Line_Performed": row.LPA_Second_Line_Performed,
                "TSA_First_Line_Performed": row.TSA_First_Line_Performed,
                "TSA_Second_Line_Performed": row.TSA_Second_Line_Performed,
                **common_response_fields(ctx),
            }
        ]
    except Exception as exc:
        return error_payload(exc)
