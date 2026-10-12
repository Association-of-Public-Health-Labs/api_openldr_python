def add_tb_common_args(
    parser,
    *,
    include_health_facility=False,
    include_facility_type=False,
    include_month_year=False,
    include_drug=False,
    include_name_filters=False,
    include_result_type=False,
    include_sample_type=False,
    include_pagination=False,
):
    """Attach the standard TB query arguments used across controller modules."""
    parser.add_argument("interval_dates", type=lambda x: x, location="args", action="append")
    parser.add_argument("province", type=lambda x: x, location="args", action="append")
    parser.add_argument("district", type=lambda x: x, location="args", action="append")
    parser.add_argument("disaggregation", type=str, location="args")
    parser.add_argument("gene_xpert_result_type", type=str, location="args")
    parser.add_argument("type_of_laboratory", type=str, location="args")

    if include_health_facility:
        parser.add_argument("health_facility", type=str, location="args")
    if include_facility_type:
        parser.add_argument("facility_type", type=str, location="args")
    if include_month_year:
        parser.add_argument("month", type=str, location="args")
        parser.add_argument("year", type=str, location="args")
    if include_drug:
        parser.add_argument("drug", type=str, location="args")
    if include_name_filters:
        parser.add_argument("first_name", type=str, location="args")
        parser.add_argument("surname", type=str, location="args")
    if include_result_type:
        parser.add_argument("result_type", type=lambda x: x, location="args", action="append")
    if include_sample_type:
        parser.add_argument("sample_type", type=lambda x: x, location="args", action="append")
    if include_pagination:
        parser.add_argument("page", type=int, location="args", default=1)
        parser.add_argument("per_page", type=int, location="args", default=50)

    return parser
