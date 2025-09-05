from fastapi import FastAPI
from dotenv import load_dotenv
from fastapi.openapi.utils import get_openapi
import os

from .routers import articles, admin, actions
from .routers import files
from . import db


def create_app() -> FastAPI:
    # Load environment variables from a .env in the current working directory
    load_dotenv()
    app = FastAPI(title="dashit API", version="0.1.0", openapi_url="/openapi.json")

    @app.on_event("startup")
    def ensure_schema():
        # Create table if it doesn't exist to avoid first-run errors
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS rss_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash TEXT UNIQUE,
                source TEXT,
                url TEXT,
                headline TEXT,
                summary TEXT,
                published TEXT,
                posted INTEGER DEFAULT 0
            )
            """
        )

    app.include_router(admin.router)
    app.include_router(articles.router)
    app.include_router(actions.router)
    app.include_router(files.router)

    # Customize OpenAPI schema: force 3.1.1 and include servers list
    def custom_openapi():
        if getattr(app, "_custom_openapi_schema", None):
            return app._custom_openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
        )
        schema["openapi"] = "3.1.1"
        # Support multiple servers; comma-separated in API_BASE_URLS, or single API_BASE_URL
        env_urls = os.getenv("API_BASE_URLS") or os.getenv("API_BASE_URL") or ""
        urls = [u.strip() for u in env_urls.split(",") if u.strip()]

        if not urls:
            urls = [
                "https://api.lexkynews.com",
            ]

        # Optionally prefer a relative server to satisfy strict origins (e.g., GPT Actions)
        use_relative = os.getenv("OPENAPI_RELATIVE_SERVER", "0").lower() in {
            "1",
            "true",
            "yes",
        }
        single_only = os.getenv("OPENAPI_SINGLE_SERVER", "1").lower() in {
            "1",
            "true",
            "yes",
        }

        servers = []
        if use_relative:
            servers = [{"url": "/"}]
        else:
            # De-duplicate while preserving order
            seen = set()
            for u in urls:
                if u not in seen:
                    seen.add(u)
                    servers.append({"url": u})
            if single_only and servers:
                servers = [servers[0]]
        schema["servers"] = servers
        app._custom_openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[assignment]

    return app


app = create_app()
