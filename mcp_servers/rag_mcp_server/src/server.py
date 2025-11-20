import os
import logging
from typing import Optional

from langchain_postgres import PGVector
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.vectorstores import VectorStoreRetriever


from fastmcp import FastMCP

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
COLLECTION_NAME: str = "knowledge_base_store"
try:
    DATABASE_URL = os.environ["DATABASE_URL"]
except KeyError:
    logger.critical("FATAL: DATABASE_URL environment variable not set. RAG server cannot start.")
    DATABASE_URL = None

retriever: Optional[VectorStoreRetriever] = None

mcp = FastMCP(
    name="RAG Knowledge Base Server",
)


def setup_retriever() -> Optional[VectorStoreRetriever]:
    """
    Connects to the pre-computed vector store in PostgreSQL and returns a
    retriever object.

    Returns:
        A configured LangChain VectorStoreRetriever, or None if an error occurs.
    """
    logger.info("Initializing RAG retriever from existing vector store...")

    if not DATABASE_URL:
        logger.error("No DATABASE_URL configured. Retriever unavailable.")
        return None

    logger.info(f"Loading local embedding model: '{EMBEDDING_MODEL_NAME}'...")
    try:
        embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
    except Exception as e:
        logger.error(f"Failed to load embedding model: {e}")
        return None
    logger.info("Embedding model loaded.")

    logger.info(f"Connecting to vector store collection: '{COLLECTION_NAME}'...")
    try:
        vectorstore = PGVector(
            connection_string=DATABASE_URL,
            embedding_function=embeddings,
            collection_name=COLLECTION_NAME,
            use_jsonb=True
        )

        logger.info("Validating vector store connection...")
        vectorstore.similarity_search("test", k=1)
        logger.info("Vector store connection validated.")

    except Exception as e:
        logger.error(f"Failed to connect to or query vector store: {e}")
        logger.error("Please ensure the index has been built using 'build_index.py'.")
        return None

    logger.info("Successfully connected to vector store.")
    return vectorstore.as_retriever()


@mcp.tool()
def query_knowledge_base(query: str) -> str:
    global retriever
    if retriever is None:
        return "Error: The knowledge base retriever is not available or failed to initialize."
    logger.info(f"Querying knowledge base with: '{query}'")
    results = retriever.invoke(query)
    if not results:
        return "No relevant information found in the knowledge base."
    formatted_results = "\n\n---\n\n".join([doc.page_content for doc in results])
    return f"Found the following information in the knowledge base:\n\n{formatted_results}"


def main() -> None:
    global retriever
    logger.info("Starting RAG MCP Server setup...")
    retriever = setup_retriever()

    if retriever:
        logger.info("🚀 RAG server starting (SSE)...")
    else:
        logger.error("No retriever was created. The server will start with no active tools.")

    mcp.run(
        transport="sse",
        host="0.0.0.0",
        port="8002"
    )


if __name__ == "__main__":
    main()