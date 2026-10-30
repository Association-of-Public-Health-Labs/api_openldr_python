from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid

from bs4 import BeautifulSoup

from auth.auth_service import get_user_by_id_service
from utilities.email_service import deliver_email, valid_email
from utilities.service_helpers import InvalidParameter


RECIPIENTS = (
    "irzelindo.salvador@moz.aphl.org",
    "diosdelio.malamule@moz.aphl.org",
    "vagner.ermelindo@moz.aphl.org",
)


def _text(payload, key, limit, required=False):
    value = payload.get(key, "")
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise InvalidParameter(f"{key} must be a {'non-empty ' if required else ''}string of at most {limit} characters")
    return value.strip()


def send_suggestion(payload, *, is_doubt, module, user_id, user_info):
    if not isinstance(payload, dict):
        raise InvalidParameter("The JSON payload must be an object")
    content = _text(payload, "content", 100000, required=True)
    title = _text(payload, "reportTitle", 250, required=True)
    category = _text(payload, "category", 20)
    supplied_email = _text(payload, "userEmail", 254)
    supplied_name = _text(payload, "userName", 250)
    if category and category not in {"doubt", "suggestion"}:
        raise InvalidParameter("category must be doubt or suggestion")
    if any(char in title for char in "\r\n"):
        raise InvalidParameter("reportTitle must not contain line breaks")

    # HTML from the editor is rendered as text in email, preserving the message
    # without executing scripts or loading remote content in the recipients' inboxes.
    soup = BeautifulSoup(content, "html.parser")
    for element in soup(["script", "style"]):
        element.decompose()
    content_text = soup.get_text(separator="\n", strip=True).replace("\xa0", " ").strip()
    if not content_text:
        raise InvalidParameter("content must contain text")

    if not user_id or user_id == "None":
        raise InvalidParameter("The authenticated user has no user_id")
    user = get_user_by_id_service(user_id)
    # The caller cannot select arbitrary CC recipients via userEmail in JSON.
    email = (user.email if user else None) or user_info.get("email_address")
    if not valid_email(email):
        raise InvalidParameter("The authenticated user has no valid email address")
    if user:
        name = " ".join(part for part in (user.first_name, user.last_name) if part) or user.user_name
    else:
        name = user_info.get("full_name") or " ".join(
            part for part in (user_info.get("first_name"), user_info.get("last_name")) if part
        ) or user_info.get("user_name") or user_id

    kind = "Dúvida" if is_doubt else "Sugestão"
    effective_category = "doubt" if is_doubt else "suggestion"
    message = EmailMessage()
    message["To"] = ", ".join(RECIPIENTS)
    message["Cc"] = email
    message["Reply-To"] = email
    message["Subject"] = f"[OpenLDR][{module}] {kind} - {title}"
    message["Date"] = format_datetime(datetime.now(timezone.utc))
    message["Message-ID"] = make_msgid()
    message.set_content(
        f"{kind} enviada a partir da dashboard OpenLDR\n\n"
        f"Módulo: {module}\nRelatório: {title}\nCategoria: {effective_category}\n"
        f"Utilizador: {name}\nUser ID: {user_id}\nEmail: {email}\n\n"
        f"Mensagem:\n{content_text}\n\n"
        f"Dados enviados pela dashboard:\nuserName: {supplied_name}\n"
        f"userEmail: {supplied_email}\ncategory: {category}\n\n"
        f"content (HTML original):\n{content}\n"
    )
    deliver_email(message)
