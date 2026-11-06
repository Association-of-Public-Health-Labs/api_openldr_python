import logging

from db.database import db
from usage.models import UsageEvent

logger = logging.getLogger(__name__)

PAGE_MAX_LENGTH = 250


def clean_page(page):
    """The path only: no query string or fragment, trimmed, cut to the column width."""
    return page.split("?", 1)[0].split("#", 1)[0].strip()[:PAGE_MAX_LENGTH]


def record_page_view(user_id, dashboard, page):
    """Store one page view. Tracking never breaks the caller, so a failure is logged and swallowed."""
    try:
        db.session.add(UsageEvent(user_id=user_id, dashboard=dashboard, page=clean_page(page)))
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Could not record page view for dashboard %s", dashboard)
