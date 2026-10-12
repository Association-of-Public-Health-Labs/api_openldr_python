"""
Verify a real Clerk session token against this API's configured
CLERK_ISSUER / CLERK_JWTS_URL / CLERK_AUTHORIZED_PARTIES.

Run it on the API host (or with the production environment loaded) BEFORE
deploying the JWT-verification change, using a token copied from a signed-in
dashboard tab (browser console: ``await window.Clerk.session.getToken()``):

    python -m tools.check_clerk_token < token.txt

The token is read from stdin so it does not end up in shell history, and it
is never printed. Exit code 0 = verified, 1 = rejected.
"""

import sys

from configs import paths
from utilities.token_verification import TokenVerificationError, verify_bearer_token

SHOWN_CLAIMS = ["iss", "sub", "azp", "iat", "exp"]


def main(argv=None, stdin=sys.stdin):
    token = stdin.read().strip()
    print(f"CLERK_ISSUER             = {paths.CLERK_ISSUER!r}")
    print(f"CLERK_JWTS_URL           = {paths.CLERK_JWTS_URL!r}")
    print(f"CLERK_AUTHORIZED_PARTIES = {paths.CLERK_AUTHORIZED_PARTIES!r}")

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
