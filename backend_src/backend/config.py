import os

# --- Database Configuration ---
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@db:5432/metrics")

# --- MCP Server URLs ---
# This structure is now ready for the MultiServerMCPClientSync
MCP_SERVER_URLS = {
    "cyberchef_api": {
        "url": os.environ.get("MCP_CYBERCHEF_URL", "http://cyberchef_api:8001"),
        "transport": "sse" # Assuming SSE transport
    },
    "rag_server": {
        "url": os.environ.get("MCP_RAG_URL", "http://rag_server:8002"),
        "transport": "sse"
    }
}


# --- CORS Origins ---
CORS_ORIGINS = [
    "http://localhost:3001",
    "http://frontend:3001",
]

# You can add other configurations here, like secret keys, etc.
TOKEN_SECRET_KEY = os.environ.get("TOKEN_SECRET_KEY", "a-secure-default-secret-for-dev")
