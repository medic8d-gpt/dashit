#!/usr/bin/env python3
"""
Check Reddit authentication using env (.env at repo root).
Prints safe info and verifies login with reddit.user.me().
"""
from __future__ import annotations

import os
import sys
import unicodedata

import praw
from dotenv import load_dotenv


def build_reddit_config() -> dict[str, str]:
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT")
    refresh_token = os.getenv("REDDIT_REFRESH_TOKEN")
    username = os.getenv("REDDIT_USERNAME")
    password = os.getenv("REDDIT_PASSWORD")

    missing = [k for k, v in {
        "REDDIT_CLIENT_ID": client_id,
        "REDDIT_CLIENT_SECRET": client_secret,
        "REDDIT_USER_AGENT": user_agent,
    }.items() if not v]
    if missing:
        raise RuntimeError("Missing env: " + ", ".join(missing))

    safe_ua = unicodedata.normalize("NFKD", user_agent).encode("ascii", "ignore").decode("ascii")

    cfg: dict[str, str] = {
        "client_id": client_id,  # type: ignore[arg-type]
        "client_secret": client_secret,  # type: ignore[arg-type]
        "user_agent": safe_ua,  # type: ignore[arg-type]
    }
    if refresh_token:
        cfg["refresh_token"] = refresh_token
    else:
        if not username or not password:
            raise RuntimeError("Provide REDDIT_REFRESH_TOKEN or REDDIT_USERNAME and REDDIT_PASSWORD")
        cfg["username"] = username
        cfg["password"] = password
    return cfg


def main():
    # Load .env from repo root
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(repo_root, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        load_dotenv()

    try:
        cfg = build_reddit_config()
    except Exception as e:
        print("config error:", e)
        sys.exit(2)

    cid = cfg.get("client_id", "")
    mode = "refresh" if "refresh_token" in cfg else "password"
    print(f"Using client_id={cid[:6]}… mode={mode} ua={cfg.get('user_agent','')}")

    try:
        reddit = praw.Reddit(**cfg)
        me = reddit.user.me()
        print("Login OK as:", me)
        # Optionally print scopes
        try:
            scopes = reddit.auth.scopes()
            print("Scopes:", sorted(list(scopes)))
        except Exception:
            pass
        sys.exit(0)
    except Exception as e:
        print("login error:", e)
        if "401" in str(e) or "invalid_grant" in str(e):
            print("Hint: App type must be 'script'; client id/secret and bot username/password must match; 2FA must be OFF for password auth. Or set REDDIT_REFRESH_TOKEN.")
        sys.exit(1)


if __name__ == "__main__":
    main()
