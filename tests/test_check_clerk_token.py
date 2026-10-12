"""The operator tool must report success/failure without printing the token."""
import io

from tests.test_token_verification import ISSUER, make_clerk_token, make_jwks
from configs import paths
from tools import check_clerk_token
from utilities import token_verification as tv


def _configure(monkeypatch):
    monkeypatch.setattr(paths, "CLERK_ISSUER", ISSUER)
    monkeypatch.setattr(paths, "CLERK_AUTHORIZED_PARTIES", None)
    monkeypatch.setattr(tv, "_clerk_jwks", tv.JwksCache(make_jwks))


def test_valid_token_exits_zero_and_prints_claims(monkeypatch, capsys):
    _configure(monkeypatch)
    token = make_clerk_token()
    code = check_clerk_token.main([], stdin=io.StringIO(token + "\n"))
    out = capsys.readouterr().out
    assert code == 0
    assert "VERIFIED" in out
    assert "user_abc" in out
    assert token not in out


def test_bad_token_exits_one_with_reason(monkeypatch, capsys):
    _configure(monkeypatch)
    code = check_clerk_token.main([], stdin=io.StringIO("not-a-jwt\n"))
    out = capsys.readouterr().out
    assert code == 1
    assert "REJECTED" in out
    assert "malformed token" in out
