"""Usage tracking and admin reports for the admin dashboard."""
from usage.controller import (
    RecordAdminAudit,
    RecordPageView,
    UsageActiveUsersByMonth,
    UsageByDashboard,
    UsagePatientAccess,
    UsageSummary,
    UsageTopPages,
    UsageTopUsers,
)


def usage_routes(api):
    api.add_resource(RecordPageView, "/usage/events", endpoint="usage_events", strict_slashes=False)
    api.add_resource(UsageSummary, "/usage/summary/", endpoint="usage_summary", strict_slashes=False)
    api.add_resource(UsageActiveUsersByMonth, "/usage/active_users_by_month/", endpoint="usage_active_users_by_month", strict_slashes=False)
    api.add_resource(UsageByDashboard, "/usage/by_dashboard/", endpoint="usage_by_dashboard", strict_slashes=False)
    api.add_resource(UsageTopUsers, "/usage/top_users/", endpoint="usage_top_users", strict_slashes=False)
    api.add_resource(UsageTopPages, "/usage/top_pages/", endpoint="usage_top_pages", strict_slashes=False)
    api.add_resource(UsagePatientAccess, "/usage/patient_access/", endpoint="usage_patient_access", strict_slashes=False)
    api.add_resource(RecordAdminAudit, "/admin/audit", endpoint="admin_audit", strict_slashes=False)
