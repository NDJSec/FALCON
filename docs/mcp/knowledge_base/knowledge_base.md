# Local Knowledge Base

## 1. Overview

This Python server provides a network-accessible interface to a Retrieval-Augmented Generation (RAG) knowledge base. 
It uses `FastMCP` (Fast Model Context Protocol) to expose a single tool: `query_knowledge_base`.

The server's primary function is to:

1. Connect to a pre-existing PostgreSQL database containing a `PGVector` vector store.

2. Load a specific Hugging Face embedding model (`all-MiniLM-L6-v2`) to understand queries.

3. Expose a tool that takes a natural language query, searches the vector store for relevant documents, and returns the findings as a formatted string.

This server is a **read-only** component; it retrieves knowledge. It does not add to, create, or update the knowledge base.

## 2. Prerequisites

Before running this server, you must have the following in place:

1. A Running PostgreSQL Database: This server requires a PostgreSQL instance (version 15+ recommended) with the pgvector extension enabled.

2. A Pre-Built Vector Store: The server connects to an existing vector store. It does not create one. You must have a separate process (e.g., a build_index.py script) that has already processed your documents and saved them to the PGVector collection. 
    * Collection Name: The server expects the collection to be named knowledge_base_store.

    * Embedding Model: The pre-built index must have been created using the exact same embedding model: all-MiniLM-L6-v2. Using a different model will result in nonsensical results.

3. Python Dependencies: The required Python packages must be installed:
    * fastmcp
    * langchain-postgres
    * langchain-huggingface
    * sentence-transformers (a dependency of langchain-huggingface)
    * psycopg (or psycopg2-binary)

All prerequisites are handled automatically by the `Dockerfile` and `pyproject.toml` files.

## 3.Configuration

The server is configured using a single, mandatory environment variable:

* `DATABASE_URL`

This variable must contain the full connection string for your PostgreSQL database. The script will fail to start if this variable is not set.

Example DATABASE_URL:

```aiignore
# Format: postgresql+<driver>://<user>:<password>@<host>:<port>/<database_name>
export DATABASE_URL="postgresql+psycopg://postgres:mysecretpassword@localhost:5432/rag_db"
```

This is handled in the `docker-compose.yaml` file. To change this value it is recommended you change it there to avoid
breaking issues. 

## 4. Running the Server

This is handled automatically through the `docker-compose.yaml` file and the server's corresponding `Dockerfile`.
To run it manually, follow the steps below:


### 1. Set the environment variable
```shell
export DATABASE_URL="postgresql+psycopg://user:pass@host/db"
```

### 2. Run the server
```shell
python rag_server.py
```


On successful startup, you will see logs indicating the connection to the vector store was successful, followed by the server startup message:

```aiignore
INFO - Successfully connected to vector store.
INFO - 🚀 RAG server starting (SSE)...

```

The server will run on `0.0.0.0:8002` and communicate using Server-Sent Events (SSE).

## 5. How to Use (API)

The server exposes one tool via FastMCP.

***Tool**:* `query_knowledge_base`

* **Description**: Queries the knowledge base for information relevant to the input query.
* **Parameter**:
    * `query`(str): The natural language query (e.g., "How do I configure the database?").

* Returns:

    * **Success:** A string containing the formatted results found in the knowledge base. Documents are separated by \n\n---\n\n.

    * **No Results:** The string "No relevant information found in the knowledge base."

    * **Error:** The string "Error: The knowledge base retriever is not available or failed to initialize."

Example: curl

You can test the running server using curl. This command sends a POST request to the /sse endpoint, specifying the tool and its arguments. The -N (no-buffering) flag is important for SSE.
```shell
curl -N -X POST http://localhost:8002/sse \
-H "Content-Type: application/json" \
-d '{
    "tool_name": "query_knowledge_base",
    "kwargs": {
        "query": "What is the process for building the index?"
    }
}'
```


Example Output (SSE stream):
```aiignore
event: tool_call
data: {"tool_name": "query_knowledge_base", "kwargs": {"query": "What is the process for building the index?"}}

event: tool_response
data: {"tool_name": "query_knowledge_base", "response": "Found the following information in the knowledge base:\n\nThe index building process involves...\n\n---\n\nTo build the index, first run the `build_index.py` script..."}

event: end
data: {}
```


## 6. Troubleshooting

| Error Log Message                                                                       | Meaning                                                                                       | Solution                                                                                                                                                                                                                                                            |
|-----------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| FATAL: DATABASE_URL environment variable not set.                                       | The script could not find the DATABASE_URL environment variable.                              | Set the DATABASE_URL environment variable before running the script. See Section 3.                                                                                                                                                                                 |
| Failed to load embedding model                                                          | The all-MiniLM-L6-v2 model could not be downloaded or loaded.                                 | Check your internet connection. Ensure you have disk space and permissions in the Hugging Face cache directory.                                                                                                                                                     |
| Failed to connect to or query vector store                                              | The script connected to the database but failed to query the knowledge_base_store collection. | 1. Verify the DATABASE_URL is correct. 2. Ensure PostgreSQL is running. 3. Confirm the pgvector extension is enabled. 4. Most likely: The knowledge_base_store collection does not exist or is empty. You must run the build_index.py (or equivalent) script first. |
| Server starts, but query_knowledge_base returns Error: ...retriever is not available... | setup_retriever() failed during server startup.                                               | Check the server's startup logs. You will find one of the other errors listed here, which prevented the retriever from being initialized.                                                                                                                           |