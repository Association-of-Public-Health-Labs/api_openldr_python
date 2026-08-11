from sqlalchemy import case, func

from tb.cultura.models.tb_cultura_model import TBCultura
from tb.cultura.services.tb_cultura_services_common import (
    RESISTANCE_DETECTED_VALUES,
    RESISTANCE_NOT_DETECTED_VALUES,
    base_filters,
    common_response_fields,
    count_if,
    error_payload,
    get_request_context,
)


RESISTANCE_FIELDS = {
    "isoniazid": TBCultura.LPAIsoniazidResult,
    "rifampicin": TBCultura.LPARifampicinResult,
    "fluoroquinolone": TBCultura.LPA2FluoroquinoloneResult,
    "amikacin": TBCultura.TSA2AmikacinResult,
    "kanamycin": TBCultura.TSA2KanamycinResult,
    "capreomycin": TBCultura.TSA2CapreomycinResult,
    "ethambutol": TBCultura.TSAEthambutolResult,
    "pyrazinamide": TBCultura.TSAPyrazinamideResult,
    "streptomycin": TBCultura.TSAStreptomycinResult,
    "levofloxacin": TBCultura.TSA2LevofloxacinResult,
    "moxifloxacin": TBCultura.TSA2MoxifloxacinResult,
    "ofloxacin": TBCultura.TSA2OfloxacinResult,
    "bedaquiline": TBCultura.TSA2BedaquilineResult,
    "clofazimine": TBCultura.TSA2ClofazimineResult,
    "linezolid": TBCultura.TSA2LinezolidResult,
}


def _row_for_drug(drug, column, filters):
    value = func.upper(func.coalesce(column, ""))
    row = (
        TBCultura.query.with_entities(
            count_if(column.isnot(None), "Tested"),
            count_if(value.in_(RESISTANCE_DETECTED_VALUES), "Resistance_Detected"),
            count_if(
                value.in_(RESISTANCE_NOT_DETECTED_VALUES),
                "Resistance_Not_Detected",
            ),
            count_if(
                (
                    column.isnot(None)
                    & value.notin_(RESISTANCE_DETECTED_VALUES)
                    & value.notin_(RESISTANCE_NOT_DETECTED_VALUES)
                ),
                "Other_Results",
            ),
        )
        .filter(*filters)
        .one()
    )

    return {
        "Drug": drug,
        "Tested": row.Tested,
        "Resistance_Detected": row.Resistance_Detected,
        "Resistance_Not_Detected": row.Resistance_Not_Detected,
        "Other_Results": row.Other_Results,
    }


def cultura_resistance_metrics_service(req_args):
    try:
        ctx = get_request_context(req_args)
        filters = base_filters(ctx)
        requested_drug = (req_args.get("drug") or "").strip().lower()
        fields = (
            {requested_drug: RESISTANCE_FIELDS[requested_drug]}
            if requested_drug in RESISTANCE_FIELDS
            else RESISTANCE_FIELDS
        )

        response = [_row_for_drug(drug, column, filters) for drug, column in fields.items()]
        for item in response:
            item.update(common_response_fields(ctx))

        return response
    except Exception as exc:
        return error_payload(exc)
