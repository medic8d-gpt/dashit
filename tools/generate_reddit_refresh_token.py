#!/usr/bin/env python3
"""
Generate a Reddit refresh token for the bot account using OAuth (localhost redirect).

Prereqs:
- In Reddit app settings, set redirect URI to: http://127.0.0.1:8765/authorize_callback

Env (.env at repo root preferred) or interactive prompts:
- REDDIT_CLIENT_ID
- REDDIT_CLIENT_SECRET
- REDDIT_USER_AGENT (e.g., "dashit/0.1 by <your_username>")

Scopes requested: identity, submit, read
"""
from __future__ import annotations

import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import praw
import unicodedata
from dotenv import load_dotenv


def main():
    # Load .env from repo root explicitly to avoid discovery issues when run from tools/
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(repo_root, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        load_dotenv()  # fallback to default search

    client_id = os.getenv("REDDIT_CLIENT_ID") or input("REDDIT_CLIENT_ID: ").strip()
    client_secret = os.getenv("REDDIT_CLIENT_SECRET") or input("REDDIT_CLIENT_SECRET: ").strip()
    user_agent = os.getenv("REDDIT_USER_AGENT") or input("REDDIT_USER_AGENT: ").strip()

    # Sanitize UA to ASCII to satisfy header encoding requirements
    user_agent = unicodedata.normalize("NFKD", user_agent).encode("ascii", "ignore").decode("ascii")

    # Match the app's configured redirect URI exactly (per your screenshot)
    redirect_uri = "http://localhost:8080"
    scopes = ["identity", "submit", "read"]

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        user_agent=user_agent,
    )

    auth_url = reddit.auth.url(scopes=scopes, state="dashit", duration="permanent")
    print("\nOpen this URL to authorize the app (permanent token):\n")
    print(auth_url)
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    code_holder = {"code": None}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            from urllib.parse import urlparse, parse_qs

            parsed = urlparse(self.path)
            # Accept any path since the app is configured for the domain root.
            qs = parse_qs(parsed.query)
            if "code" not in qs:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing code param")
                return
            code_holder["code"] = qs["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Authorization received. You can close this tab.")

        def log_message(self, format, *args):
            return

    server = HTTPServer(("127.0.0.1", 8765), Handler)

    def serve():
        server.handle_request()  # handle a single request

    t = threading.Thread(target=serve, daemon=True)
    t.start()

    print("\nWaiting for redirect to", redirect_uri)
    t.join(timeout=180)
    server.server_close()

    code = code_holder["code"]
    if not code:
        print("\nDidn't receive the callback automatically.")
        pasted = input("Paste the redirected URL (or just the 'code' param) here: ").strip()
        if "code=" in pasted:
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(pasted).query)
            code = qs.get("code", [None])[0]
        else:
            code = pasted or None
        if not code:
            print("No code provided. Aborting.")
            sys.exit(1)

    refresh = reddit.auth.authorize(code)
    print("\nYour REDDIT_REFRESH_TOKEN (store securely, not in git):\n")
    print(refresh)


if __name__ == "__main__":
    main()
