"""Suggestion contract with real JWT verification and a fake SMTP server."""

import smtplib
import configparser
import runpy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from flasgger import Swagger
from flask import Flask
from flask_restful import Api

from configs import paths
from suggestions import service
from suggestions.routes import MODULES, suggestion_routes
from tests.test_token_verification import ISSUER, TB_ORIGIN, make_clerk_token, make_jwks
from utilities import email_service, token_verification as tv
from utilities.swagger import swagger_template


PAYLOAD = {
    "content": "<p>teste</p>", "category": "doubt",
    "reportTitle": "Relatório de Resultados - Ultra",
    "userEmail": "dashboard@example.org", "userName": "Dashboard Name",
}


@pytest.fixture
def mail_env(app, monkeypatch):
    settings = {
        "SMTP_HOST": "smtp.example.org", "SMTP_PORT": 587,
        "SMTP_USERNAME": "smtp-user", "SMTP_PASSWORD": "smtp-secret",
        "SMTP_FROM_ADDRESS": "openldr@example.org", "SMTP_USE_TLS": True,
        "SMTP_USE_SSL": False, "SMTP_TIMEOUT": 15,
    }
    for key, value in settings.items():
        monkeypatch.setitem(app.config, key, value)
    lookup = MagicMock(return_value=SimpleNamespace(
        email="registered@example.org", first_name="Registered", last_name="User", user_name="registered"
    ))
    monkeypatch.setattr(service, "get_user_by_id_service", lookup)
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    smtp.send_message.return_value = {}
    factory = MagicMock(return_value=smtp)
    monkeypatch.setattr(email_service.smtplib, "SMTP", factory)
    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", factory)
    return smtp, factory, lookup


@pytest.mark.parametrize("prefix,module", MODULES.items())
@pytest.mark.parametrize("duvida,kind,category", [("true", "Dúvida", "doubt"), ("false", "Sugestão", "suggestion")])
def test_send_on_every_module(client, auth_headers, mail_env, prefix, module, duvida, kind, category):
    smtp, factory, lookup = mail_env
    response = client.post(f"{prefix}/send-suggestion?duvida={duvida}", headers=auth_headers, json=PAYLOAD)
    assert response.status_code == 200
    assert response.json["status"] == "success"
    lookup.assert_called_once_with("test-123")
    factory.assert_called_once_with("smtp.example.org", 587, timeout=15.0)
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("smtp-user", "smtp-secret")
    message = smtp.send_message.call_args.args[0]
    assert str(message["Subject"]) == f"[OpenLDR][{module}] {kind} - {PAYLOAD['reportTitle']}"
    assert set(str(message["To"]).split(", ")) == set(service.RECIPIENTS)
    assert str(message["Cc"]) == "registered@example.org"
    assert str(message["Reply-To"]) == "registered@example.org"
    assert str(message["From"]) == "openldr@example.org"
    body = message.get_content()
    for expected in ("test-123", "Registered User", "Mensagem:\nteste", "Categoria: " + category, *PAYLOAD.values()):
        assert expected in body
    assert message.get_content_type() == "text/plain"


@pytest.mark.parametrize("prefix", MODULES)
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid"}])
def test_authentication_before_email(client, mail_env, prefix, headers):
    response = client.post(f"{prefix}/send-suggestion?duvida=true", headers=headers, json=PAYLOAD)
    assert response.status_code == 401
    mail_env[0].send_message.assert_not_called()
    mail_env[2].assert_not_called()


@pytest.mark.parametrize("registered", [True, False])
def test_clerk_identity_comes_from_verified_sub(client, mail_env, monkeypatch, registered):
    monkeypatch.setattr(paths, "CLERK_ISSUER", ISSUER)
    monkeypatch.setattr(paths, "CLERK_AUTHORIZED_PARTIES", TB_ORIGIN)
    monkeypatch.setattr(tv, "_clerk_jwks", tv.JwksCache(make_jwks))
    if not registered:
        mail_env[2].return_value = None
    response = client.post("/tb/gx/send-suggestion?duvida=true", json=PAYLOAD,
                           headers={"Authorization": f"Bearer {make_clerk_token(sub='user_clerk_42')}"})
    assert response.status_code == (200 if registered else 400)
    mail_env[2].assert_called_once_with("user_clerk_42")
    if not registered:
        mail_env[0].send_message.assert_not_called()


@pytest.mark.parametrize("query", ["", "?duvida=", "?duvida=no", "?duvida=0", "?duvida=true&duvida=false"])
def test_invalid_duvida(client, auth_headers, mail_env, query):
    response = client.post("/tb/gx/send-suggestion" + query, headers=auth_headers, json=PAYLOAD)
    assert response.status_code == 400
    mail_env[0].send_message.assert_not_called()
    mail_env[2].assert_not_called()


@pytest.mark.parametrize("changes", [
    {"content": ""}, {"content": "<p>&nbsp;</p>"}, {"content": "<script>alert(1)</script>"},
    {"content": 42}, {"content": "x" * 100001}, {"reportTitle": ""},
    {"reportTitle": "x\r\nBcc: attacker@example.org"}, {"reportTitle": None},
    {"category": "invalid"}, {"userEmail": ["attacker@example.org"]},
    {"userName": {"nested": "object"}},
])
def test_invalid_payload_fields(client, auth_headers, mail_env, changes):
    response = client.post("/hiv/vl/send-suggestion?duvida=true", headers=auth_headers, json={**PAYLOAD, **changes})
    assert response.status_code == 400
    mail_env[0].send_message.assert_not_called()


@pytest.mark.parametrize("body,content_type", [
    ("{broken", "application/json"), ("null", "application/json"),
    ("[]", "application/json"), ('"text"', "application/json"), ("hello", "text/plain"),
])
def test_invalid_json(client, auth_headers, mail_env, body, content_type):
    response = client.post("/hiv/send-suggestion?duvida=false", headers=auth_headers, data=body, content_type=content_type)
    assert response.status_code == 400
    mail_env[0].send_message.assert_not_called()


def test_verified_token_email_fallback_and_trailing_slash(client, auth_headers, mail_env):
    mail_env[2].return_value = None
    response = client.post("/tb/send-suggestion/?duvida=false", headers=auth_headers, json=PAYLOAD)
    assert response.status_code == 200
    message = mail_env[0].send_message.call_args.args[0]
    assert str(message["Cc"]) == "test@openldr.org"
    assert "Utilizador: Test User" in message.get_content()


@pytest.mark.parametrize("email", [" ", "@", "invalid", "one@example.org,two@example.org", "one@example.org\r\nBcc:two@example.org"])
def test_caller_email_must_be_one_mailbox(client, auth_headers, mail_env, email):
    mail_env[2].return_value.email = email
    response = client.post("/hiv/eid/send-suggestion?duvida=true", headers=auth_headers, json=PAYLOAD)
    assert response.status_code == 400
    mail_env[0].send_message.assert_not_called()


@pytest.mark.parametrize("setting,value", [
    ("SMTP_HOST", ""), ("SMTP_FROM_ADDRESS", ""), ("SMTP_PORT", "invalid"),
    ("SMTP_TIMEOUT", 0), ("SMTP_USE_SSL", True), ("SMTP_USE_TLS", "maybe"), ("SMTP_PASSWORD", ""),
])
def test_smtp_configuration_errors(client, app, auth_headers, mail_env, monkeypatch, setting, value):
    monkeypatch.setitem(app.config, setting, value)
    response = client.post("/hiv/send-suggestion?duvida=true", headers=auth_headers, json=PAYLOAD)
    assert response.status_code == 503
    mail_env[1].assert_not_called()


@pytest.mark.parametrize("error", [smtplib.SMTPException("private smtp-secret"), OSError("private host")])
def test_smtp_failure_is_generic(client, auth_headers, mail_env, error):
    mail_env[0].send_message.side_effect = error
    response = client.post("/tb/gx/send-suggestion?duvida=true", headers=auth_headers, json=PAYLOAD)
    assert response.status_code == 502
    assert "private" not in response.get_data(as_text=True)
    assert "smtp-secret" not in response.get_data(as_text=True)


def test_partial_recipient_refusal_is_not_success(client, auth_headers, mail_env):
    mail_env[0].send_message.return_value = {service.RECIPIENTS[0]: (550, b"refused")}
    response = client.post("/tb/gx/send-suggestion?duvida=true", headers=auth_headers, json=PAYLOAD)
    assert response.status_code == 502


def test_user_lookup_failure_is_generic(client, auth_headers, mail_env):
    mail_env[2].side_effect = RuntimeError("private SQL details")
    response = client.post("/hiv/eid/send-suggestion?duvida=true", headers=auth_headers, json=PAYLOAD)
    assert response.status_code == 500
    assert "private" not in response.get_data(as_text=True)
    mail_env[0].send_message.assert_not_called()


def test_ssl_transport(client, app, auth_headers, mail_env, monkeypatch):
    monkeypatch.setitem(app.config, "SMTP_USE_SSL", True)
    monkeypatch.setitem(app.config, "SMTP_USE_TLS", False)
    monkeypatch.setitem(app.config, "SMTP_PORT", 465)
    response = client.post("/tb/gx/send-suggestion?duvida=true", headers=auth_headers, json=PAYLOAD)
    assert response.status_code == 200
    assert "context" in mail_env[1].call_args.kwargs
    mail_env[0].starttls.assert_not_called()


def test_swagger_documents_all_suggestion_paths():
    app = Flask(__name__)
    suggestion_routes(Api(app))
    Swagger(app, template=swagger_template)
    response = app.test_client().get("/apispec_1.json")
    assert response.status_code == 200
    for prefix in MODULES:
        spec = response.json["paths"][f"{prefix}/send-suggestion"]["post"]
        assert any(param["name"] == "duvida" and param["required"] for param in spec["parameters"])


def test_smtp_service_reads_paths(app, monkeypatch):
    monkeypatch.setattr(paths, "SMTP_HOST", "parsed.example.org")
    monkeypatch.setattr(paths, "SMTP_PASSWORD", "literal%password")
    with app.app_context():
        assert email_service._setting("SMTP_HOST") == "parsed.example.org"
        assert email_service._setting("SMTP_PASSWORD") == "literal%password"
        monkeypatch.setenv("SMTP_HOST", "ignored-after-parsing.example.org")
        assert email_service._setting("SMTP_HOST") == "parsed.example.org"


@pytest.mark.parametrize("system", ["Windows", "Linux"])
def test_paths_parses_smtp_configuration(monkeypatch, tmp_path, system):
    values = {
        "host": "smtp.example.org", "port": "465", "username": "smtp-user",
        "password": "literal%password", "from_address": "openldr@example.org",
        "use_tls": "false", "use_ssl": "true", "timeout": "20",
    }
    ini = tmp_path / "configs.ini"
    ini.write_text("[Email]\n" + "\n".join(f"{key}={value}" for key, value in values.items()), encoding="utf-8")
    original_read = configparser.ConfigParser.read
    monkeypatch.setattr(configparser.ConfigParser, "read", lambda self, *args, **kwargs: original_read(self, ini, **kwargs))
    monkeypatch.setattr("platform.system", lambda: system)
    for key, value in values.items():
        variable = "SMTP_" + key.upper()
        if system == "Linux":
            monkeypatch.setenv(variable, value)
        else:
            monkeypatch.delenv(variable, raising=False)
    settings = runpy.run_path(str(Path(__file__).parents[1] / "configs" / "paths.py"))
    for key, value in values.items():
        assert settings["SMTP_" + key.upper()] == value
