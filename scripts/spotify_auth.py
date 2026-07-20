"""One-time Spotify authorization helper. Run on any computer with a browser.

Prereq: create a (free) app at https://developer.spotify.com/dashboard with
Redirect URI exactly  http://127.0.0.1:8765/callback  and note its
Client ID and Client Secret. For a second person (e.g. your wife), add their
Spotify account email under the app's "User Management" first.

Usage:
    python scripts/spotify_auth.py

It opens a browser to log in (use a private window for the second account),
then prints the refresh token to put in SPOTIFY_REFRESH_TOKENS.
Requires only the Python standard library.
"""

import base64
import http.server
import json
import secrets
import threading
import urllib.parse
import urllib.request
import webbrowser

REDIRECT_URI = "http://127.0.0.1:8765/callback"
SCOPE = "user-read-playback-state"

auth_code: str | None = None
expected_state: str | None = None
done = threading.Event()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        # Verify the OAuth state we generated, so only the flow we initiated
        # can hand us a code.
        if "code" in query and query.get("state", [""])[0] == expected_state:
            auth_code = query["code"][0]
            body = b"<h2>Authorized! You can close this tab.</h2>"
        else:
            body = b"<h2>Authorization failed - check the terminal.</h2>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)
        done.set()

    def log_message(self, *args):
        pass


def main() -> None:
    client_id = input("Client ID: ").strip()
    client_secret = input("Client Secret: ").strip()

    global expected_state
    state = secrets.token_urlsafe(16)
    expected_state = state
    params = urllib.parse.urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "state": state,
        "show_dialog": "true",  # force account picker for the second person
    })
    url = f"https://accounts.spotify.com/authorize?{params}"

    server = http.server.HTTPServer(("127.0.0.1", 8765), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    print("\nOpening browser (use a private window for a second account):\n", url, "\n")
    webbrowser.open(url)
    if not done.wait(timeout=300):
        raise SystemExit("Timed out waiting for authorization.")
    server.shutdown()

    if not auth_code:
        raise SystemExit("No authorization code received.")

    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
    }).encode()
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token", data=data,
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        tokens = json.load(resp)

    print("\nSuccess! Add this to SPOTIFY_REFRESH_TOKENS as  <name>:<token>\n")
    print("Refresh token:", tokens["refresh_token"])


if __name__ == "__main__":
    main()
