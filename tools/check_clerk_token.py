"""
Verify a real Clerk session token against this API's configured
CLERK_ISSUER / CLERK_JWTS_URL / CLERK_AUTHORIZED_PARTIES.

Run it on the API host (or with the production environment loaded) BEFORE
deploying the JWT-verification change, using a token copied from a signed-in
dashboard tab (browser console: ``await window.Clerk.session.getToken()``).
Clerk session tokens live only ~60 s, so save it to a file and run the check
straight away.

bash / Linux:

    python -m tools.check_clerk_token < token.txt

Windows PowerShell (``<`` redirection is not supported there):

    python -m tools.check_clerk_token token.txt
    Get-Content token.txt | python -m tools.check_clerk_token

A file argument is read as UTF-8 (a UTF-8 BOM is ignored; a UTF-16 file with
a BOM, as written by Windows PowerShell 5 ``>``, is also accepted). A leading
BOM and surrounding whitespace are stripped from stdin as well.

The token is never printed. Besides the verification result, the tool prints
a "diagnostic (unverified)" clock-offset line: this host's time minus the
token's ``iat``. A token copied a few seconds ago should show a small
positive number; a large or negative value means this host's clock is off
(Windows: ``w32tm /query /status``).

Exit code 0 = verified, 1 = rejected.
"""

import codecs
import sys
import time

import jwt

from configs import paths
from utilities.token_verification import TokenVerificationError, verify_bearer_token

SHOWN_CLAIMS = ["iss", "sub", "azp", "iat", "exp"]


def _read_token_file(path):
    with open(path, "rb") as handle:
        raw = handle.read()
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


def _clean(text):
    return text.strip().lstrip("﻿").strip()


def _print_clock_offset(token):
    """Unverified diagnostic only: never used to accept or reject the token."""
    try:
        claims = jwt.decode(token, options={"verify_signature": False})
        iat = int(claims["iat"])
        offset = int(time.time()) - iat
        print(
            f"diagnostic (unverified): clock offset (this host now - token iat) = {offset} s"
            f" (iat={iat}, exp={claims.get('exp')})"
        )
    except Exception:
        print("diagnostic (unverified): clock offset unavailable (could not read iat)")


def main(argv=None, stdin=sys.stdin):
    argv = list(argv or [])
    if len(argv) == 1:
        token = _clean(_read_token_file(argv[0]))
    else:
        token = _clean(stdin.read())

    print(f"CLERK_ISSUER             = {paths.CLERK_ISSUER!r}")
    print(f"CLERK_JWTS_URL           = {paths.CLERK_JWTS_URL!r}")
    print(f"CLERK_AUTHORIZED_PARTIES = {paths.CLERK_AUTHORIZED_PARTIES!r}")
    _print_clock_offset(token)

    try:
        claims = verify_bearer_token(token)
    except TokenVerificationError as exc:
        print(f"REJECTED: {exc}")
        return 1

    print("VERIFIED")
    for name in SHOWN_CLAIMS:
        print(f"  {name}: {claims.get(name)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
