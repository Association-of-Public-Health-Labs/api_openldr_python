"""Query parameters and parser shared by every EID reporting controller."""

from utilities.controller_helpers import LIST_ARG, STR_ARG, build_common_parser

# lab_type and category stay strings here: parse_eid_params validates them
# (an invalid value is a 400, not a silently ignored filter).
EID_FILTER_ARGS = [
    ("lab_code", LIST_ARG),
    ("lab_type", STR_ARG),
    ("category", STR_ARG),
]

eid_parser = build_common_parser(extra_args=EID_FILTER_ARGS)
