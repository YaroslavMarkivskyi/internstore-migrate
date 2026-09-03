"""The `/oauth/login` page — the human step of the OAuth `/authorize` flow.

`provider.authorize()` redirects the browser here with an opaque `rid`; the
user signs in with their InternStore (Firebase) credentials; on success we
mint the auth code and bounce back to the MCP client's redirect_uri.
"""

import html

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.routing import Route

from mcp_gateway.oauth.firebase import FirebaseAuthClient, FirebaseAuthError
from mcp_gateway.oauth.provider import GatewayOAuthProvider

LOGIN_PATH = "/oauth/login"

_PAGE = """<!doctype html><meta charset=utf-8>
<title>Sign in — InternStore MCP</title>
<style>body{{font:15px system-ui;max-width:22rem;margin:4rem auto;padding:0 1rem}}
input{{width:100%;padding:.5rem;margin:.35rem 0;box-sizing:border-box}}
button{{padding:.55rem 1rem;margin-top:.5rem}}.err{{color:#b00020}}</style>
<h1>Authorize MCP access</h1>
<p>An MCP client wants to shop on your behalf. Sign in to allow it.</p>
{error}
<form method=post action="{action}">
<input type=hidden name=rid value="{rid}">
<input name=email type=email placeholder=Email autocomplete=username required autofocus>
<input name=password type=password placeholder=Password autocomplete=current-password required>
<button type=submit>Sign in &amp; allow</button>
</form>"""


def _render(rid: str, error: str = "") -> HTMLResponse:
    err_html = f'<p class=err>{html.escape(error)}</p>' if error else ""
    return HTMLResponse(_PAGE.format(action=LOGIN_PATH, rid=html.escape(rid), error=err_html))


def build_login_routes(provider: GatewayOAuthProvider, firebase: FirebaseAuthClient) -> list[Route]:
    async def get_login(request: Request) -> Response:
        rid = request.query_params.get("rid", "")
        if not rid:
            return HTMLResponse("<p>Missing login session.</p>", status_code=400)
        return _render(rid)

    async def post_login(request: Request) -> Response:
        form = await request.form()
        rid = str(form.get("rid", ""))
        email, password = str(form.get("email", "")), str(form.get("password", ""))
        if not rid:
            return HTMLResponse("<p>Missing login session.</p>", status_code=400)
        try:
            identity = await firebase.sign_in(email, password)
            redirect_url = provider.complete_login(rid, identity)
        except FirebaseAuthError as exc:
            return _render(rid, str(exc))
        except KeyError:
            return HTMLResponse("<p>This login session has expired. Restart the client.</p>", status_code=400)
        return RedirectResponse(redirect_url, status_code=302, headers={"Cache-Control": "no-store"})

    return [
        Route(LOGIN_PATH, get_login, methods=["GET"]),
        Route(LOGIN_PATH, post_login, methods=["POST"]),
    ]
