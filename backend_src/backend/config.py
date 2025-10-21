import os

# --- Database Configuration ---
DATABASE_URL = os.environ.get("DATABASE_URL", default="postgresql+psycopg2://postgres:postgres@db:5432/metrics")

# --- MCP Server URLs ---
MCP_SERVER_URLS = {
    "cyberchef_api": {
        "url": os.environ.get("MCP_CYBERCHEF_URL", default="http://cyberchef_api:8001"),
        "transport": "sse"
    },
    "rag_server": {
        "url": os.environ.get("MCP_RAG_URL", default="http://rag_server:8002"),
        "transport": "sse"
    }
}


# --- CORS Origins ---
CORS_ORIGINS = [
    "http://localhost:3001",
    "http://frontend:3001",
]

TOKEN_SECRET_KEY = os.environ.get("TOKEN_SECRET_KEY", default="a-secure-default-secret-for-dev")
