"""Usage tracking for the admin dashboard."""
from usage.controller import RecordPageView


def usage_routes(api):
    api.add_resource(RecordPageView, "/usage/events", endpoint="usage_events", strict_slashes=False)
