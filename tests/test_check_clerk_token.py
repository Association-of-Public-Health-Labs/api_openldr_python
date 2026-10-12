"""The operator tool must report success/failure without printing the token."""
import io

import pytest

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


# --- File argument, BOMs, clock-offset diagnostic --------------------------

import re
import time

from tests.test_token_verification import OTHER_KEY


def test_token_read_from_file_argument(monkeypatch, capsys, tmp_path):
    _configure(monkeypatch)
    token = make_clerk_token()
    path = tmp_path / "token.txt"
    path.write_text(token + "\r\n", encoding="utf-8")
    code = check_clerk_token.main([str(path)], stdin=io.StringIO("ignored"))
    out = capsys.readouterr().out
    assert code == 0
    assert "VERIFIED" in out
    assert token not in out


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16"])
def test_bom_prefixed_file_verifies(monkeypatch, capsys, tmp_path, encoding):
    _configure(monkeypatch)
    token = make_clerk_token()
    path = tmp_path / "token.txt"
    path.write_bytes((token + "\r\n").encode(encoding))
    if encoding == "utf-8-sig":
        assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    code = check_clerk_token.main([str(path)])
    out = capsys.readouterr().out
    assert code == 0, out
    assert token not in out


def test_bom_on_stdin_is_stripped(monkeypatch, capsys):
    _configure(monkeypatch)
    token = make_clerk_token()
    code = check_clerk_token.main([], stdin=io.StringIO("﻿ " + token + " \n"))
    out = capsys.readouterr().out
    assert code == 0, out
    assert token not in out


def test_clock_offset_diagnostic_printed(monkeypatch, capsys):
    _configure(monkeypatch)
    token = make_clerk_token(iat=int(time.time()) - 10)
    check_clerk_token.main([], stdin=io.StringIO(token))
    out = capsys.readouterr().out
    match = re.search(r"diagnostic \(unverified\).*clock offset.*?(-?\d+) s", out)
    assert match, out
    assert 9 <= int(match.group(1)) <= 15


def test_rejected_token_never_printed_and_still_shows_diagnostic(monkeypatch, capsys):
    _configure(monkeypatch)
    token = make_clerk_token(private_key=OTHER_KEY)
    code = check_clerk_token.main([], stdin=io.StringIO(token))
    out = capsys.readouterr().out
    assert code == 1
    assert "REJECTED" in out
    assert "diagnostic (unverified)" in out
    assert token not in out
    for part in token.split("."):
        assert part not in out


def test_malformed_token_still_rejected_cleanly(monkeypatch, capsys):
    _configure(monkeypatch)
    code = check_clerk_token.main([], stdin=io.StringIO("not-a-jwt"))
    out = capsys.readouterr().out
    assert code == 1
    assert "REJECTED" in out
    assert "not-a-jwt" not in out
