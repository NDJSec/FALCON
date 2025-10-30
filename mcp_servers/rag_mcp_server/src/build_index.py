import os
import sys
import gc
import logging
import multiprocessing
from pathlib import Path
from itertools import chain
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

# --- Vector Store + Embeddings ---
from langchain_community.vectorstores import PGVector
from langchain_huggingface import HuggingFaceEmbeddings

# --- Document Loaders ---
from langchain_community.document_loaders import (
    PyPDFLoader,
    UnstructuredMarkdownLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from document_loaders import SVDLoader  # Your custom loader

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# --- Configuration ---
KNOWLEDGE_BASE_DIR = "/app/knowledge_base"
COLLECTION_NAME = "knowledge_base_store"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 10_000  # commit every 2000 chunks
MAX_WORKERS = min(8, os.cpu_count() or 4)

# --- Database URL ---
try:
    DATABASE_URL = os.environ["DATABASE_URL"].replace("postgresql+psycopg2://", "postgresql://")
except KeyError:
    logger.critical("FATAL: DATABASE_URL not set.")
    sys.exit(1)


# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------
def clean_text(text: str) -> str:
    """Removes NUL and invisible characters to prevent DB insert errors."""
    return text.replace("\x00", "").strip() if text else ""


# ------------------------------------------------------------
# Document Processing
# ------------------------------------------------------------
def process_file_streaming(file_path: Path, splitter: RecursiveCharacterTextSplitter):
    """Yields split documents progressively to reduce memory usage."""
    try:
        if file_path.suffix == ".pdf":
            loader = PyPDFLoader(str(file_path))
        elif file_path.suffix == ".md":
            loader = UnstructuredMarkdownLoader(str(file_path))
        elif file_path.suffix == ".svd":
            loader = SVDLoader(str(file_path), max_workers=1)
        else:
            logger.warning(f"Skipping unsupported file type: {file_path}")
            return

        for doc in loader.lazy_load():
            for split in splitter.split_documents([doc]):
                split.page_content = clean_text(split.page_content)
                if split.page_content:
                    yield split

    except Exception as e:
        logger.error(f"Failed processing {file_path}: {e}")


# ------------------------------------------------------------
# Batch Writer (Runs in Subprocess)
# ------------------------------------------------------------
def _write_batch_subprocess(args):
    """Runs in a separate process to free memory after each batch."""
    docs, db_url, first_batch, embed_model_name, collection_name = args

    try:
        embeddings = HuggingFaceEmbeddings(model_name=embed_model_name)
        PGVector.from_documents(
            documents=docs,
            embedding=embeddings,
            connection_string=db_url,
            collection_name=collection_name,
            pre_delete_collection=first_batch,
            use_jsonb=True,
        )
        logger.info(f"✅ Subprocess wrote {len(docs)} chunks to DB (first_batch={first_batch})")
    except Exception as e:
        logger.error(f"❌ Subprocess failed to write batch: {e}", exc_info=True)
        raise


def write_batch_to_db(docs: List[Document], first_batch: bool):
    """Spawns subprocess for memory-safe batch writing."""
    if not docs:
        return
    proc = multiprocessing.get_context("spawn").Process(
        target=_write_batch_subprocess,
        args=((docs, DATABASE_URL, first_batch, EMBEDDING_MODEL_NAME, COLLECTION_NAME),),
    )
    proc.start()
    proc.join()

    if proc.exitcode != 0:
        raise RuntimeError(f"Subprocess exited with code {proc.exitcode}")

    logger.info(f"Batch of {len(docs)} written and subprocess cleaned up.")
    gc.collect()  # reclaim parent memory


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():
    logger.info("--- 🚀 Starting Knowledge Base Index Build ---")

    kb_dir = Path(KNOWLEDGE_BASE_DIR)
    if not kb_dir.is_dir():
        logger.critical(f"Knowledge base directory '{KNOWLEDGE_BASE_DIR}' does not exist.")
        sys.exit(1)

    # --- Find all supported documents ---
    pdfs = list(kb_dir.rglob("*.pdf"))
    mds = list(kb_dir.rglob("*.md"))
    svds = list(chain(kb_dir.rglob("*.svd"), kb_dir.rglob("*.xml")))
    all_files = list(chain(pdfs, mds, svds))
    if not all_files:
        logger.warning("No documents found. Exiting.")
        return
    logger.info(f"Found {len(all_files)} total documents to process.")

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    logger.info(f"Processing with {MAX_WORKERS} threads, batch size={BATCH_SIZE}")

    buffer: List[Document] = []
    first_batch = True
    processed_files = 0
    total_chunks = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(list, process_file_streaming(file, splitter)): file for file in all_files}

        for future in as_completed(futures):
            file = futures[future]
            try:
                splits = future.result()
            except Exception as e:
                logger.error(f"❌ Error in {file}: {e}")
                continue

            if not splits:
                logger.warning(f"No splits for {file}")
                continue

            processed_files += 1
            for split in splits:
                buffer.append(split)
                total_chunks += 1

                if len(buffer) >= BATCH_SIZE:
                    write_batch_to_db(buffer, first_batch)
                    buffer.clear()
                    first_batch = False
                    logger.info(f"Progress: {processed_files}/{len(all_files)} files, {total_chunks} chunks so far.")

            logger.info(f"Finished processing {file} ({len(splits)} splits).")

    # --- Write final batch ---
    if buffer:
        logger.info(f"Final flush: writing last {len(buffer)} chunks...")
        write_batch_to_db(buffer, first_batch)

    logger.info(f"🎉 Index build complete! Processed {processed_files} files, {total_chunks} total chunks.")


# ------------------------------------------------------------
if __name__ == "__main__":
    multiprocessing.set_start_method("spawn", force=True)
    main()
