import os
import sys
import time
import logging
from sqlalchemy import create_engine, text, exc

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- Config ---
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    logger.critical("FATAL: DATABASE_URL environment variable not set.")
    sys.exit(1)

COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "knowledge_base_store")
DB_RETRY_COUNT = 15
DB_RETRY_DELAY = 5  # seconds


def wait_for_db(engine):
    """Wait until database connection is available."""
    logger.info("⏳ Waiting for database connection...")
    for i in range(DB_RETRY_COUNT):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ Database connection successful.")
            return True
        except exc.OperationalError:
            logger.warning(f"Database not ready. Retrying in {DB_RETRY_DELAY}s... ({i + 1}/{DB_RETRY_COUNT})")
            time.sleep(DB_RETRY_DELAY)
    logger.error(f"❌ Failed to connect to database after {DB_RETRY_COUNT} retries.")
    return False


def ensure_vector_extension(engine):
    """Ensure the pgvector extension is enabled."""
    logger.info("🔍 Checking 'vector' extension...")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT extname FROM pg_extension;")).fetchall()
            if any("vector" in row[0] for row in result):
                logger.info("✅ 'vector' extension already enabled.")
            else:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector CASCADE;"))
                logger.info("✅ 'vector' extension installed successfully.")
    except Exception as e:
        logger.critical(f"FATAL: Failed to verify/create 'vector' extension: {e}")
        sys.exit(1)


def collection_exists(engine):
    """Check whether the target LangChain PG collection exists."""
    logger.info(f"🔍 Checking if collection '{COLLECTION_NAME}' exists...")
    query = text(
        "SELECT EXISTS (SELECT 1 FROM langchain_pg_collection WHERE name = :collection_name);"
    )
    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"collection_name": COLLECTION_NAME}).scalar()
        if result:
            logger.info(f"✅ Collection '{COLLECTION_NAME}' exists.")
        else:
            logger.info(f"❌ Collection '{COLLECTION_NAME}' not found.")
        return result
    except exc.ProgrammingError as e:
        if "does not exist" in str(e):
            logger.warning("⚠️ langchain_pg_collection table not found — assuming first run.")
            return False
        logger.error(f"Unexpected database error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error checking collection: {e}")
        sys.exit(1)


def build_index():
    """Run the build_index.py script."""
    logger.info("🧱 Running build_index.py to build vector index...")
    result = os.system("python src/build_index.py")
    if result != 0:
        logger.critical("FATAL: build_index.py failed.")
        sys.exit(1)
    logger.info("✅ build_index.py completed successfully.")


def start_server():
    """Replace this process with the RAG server process."""
    logger.info("🚀 Starting RAG MCP server (__main__.py)...")
    os.execvp(sys.executable, [sys.executable, "__main__.py"])  # replaces process fully


def main():
    db_url = DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://")
    engine = create_engine(db_url)

    if not wait_for_db(engine):
        sys.exit(1)

    ensure_vector_extension(engine)

    if not collection_exists(engine):
        build_index()

    # Replace current process with the real server
    start_server()


if __name__ == "__main__":
    main()
