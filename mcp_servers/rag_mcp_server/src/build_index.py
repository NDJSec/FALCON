import os
import sys
import gc
import logging
import multiprocessing
import threading
import queue
from pathlib import Path
from itertools import chain
from concurrent.futures import ThreadPoolExecutor
from typing import List

from langchain_postgres import PGVector
from langchain_huggingface import HuggingFaceEmbeddings

from langchain_community.document_loaders import (
    PyPDFLoader,
    UnstructuredMarkdownLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from document_loaders import SVDLoader
from document_loaders import DTSLoader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

KNOWLEDGE_BASE_DIR = "/app/knowledge_base"
COLLECTION_NAME = "knowledge_base_store"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

EMBED_BATCH_SIZE = 256

FILE_LOADER_THREADS = min(8, os.cpu_count() or 4)

WRITER_PROCESSES = max(1, (os.cpu_count() or 2) // 2)

SPLIT_QUEUE_MAXSIZE = EMBED_BATCH_SIZE * (WRITER_PROCESSES * 4 + 2)

try:
    DATABASE_URL = os.environ["DATABASE_URL"].replace("postgresql+psycopg2://", "postgresql://")
except KeyError:
    logger.critical("FATAL: DATABASE_URL not set.")
    sys.exit(1)


def clean_text(text: str) -> str:
    """Removes NUL and invisible characters to prevent DB insert errors."""
    return text.replace("\x00", "").strip() if text else ""


def process_file_streaming(file_path: Path, splitter: RecursiveCharacterTextSplitter):
    """
    Yields split documents progressively to reduce memory usage.
    Same semantics as your original function.
    """
    try:
        if file_path.suffix == ".pdf":
            loader = PyPDFLoader(str(file_path))
        elif file_path.suffix == ".md":
            loader = UnstructuredMarkdownLoader(str(file_path))
        elif file_path.suffix == ".svd":
            loader = SVDLoader(str(file_path), max_workers=1)
        elif file_path.suffix == ".dts":
            loader = DTSLoader(str(file_path))
        else:
            logger.warning(f"Skipping unsupported file type: {file_path}")
            return

        for doc in loader.lazy_load():
            for split in splitter.split_documents([doc]):
                split.page_content = clean_text(split.page_content)
                if split.page_content:
                    yield split

    except Exception:
        logger.exception(f"Failed processing {file_path}")
        # Let the caller handle progress; on exception, stop this file's production.
        return


def writer_process_worker(docs_serialized, db_url, first_batch, embed_model_name, collection_name):
    """
    This function runs in a separate process (spawned by multiprocessing.Pool).
    It reconstructs the Document objects (if necessary), computes embeddings in batch,
    and calls PGVector.from_documents (which handles DB insert).
    """
    try:
        embeddings = HuggingFaceEmbeddings(model_name=embed_model_name)
        docs = []
        for d in docs_serialized:
            if isinstance(d, Document):
                docs.append(d)
            else:
                docs.append(Document(page_content=d["page_content"], metadata=d.get("metadata")))
        PGVector.from_documents(
            documents=docs,
            embedding=embeddings,
            connection_string=db_url,
            collection_name=collection_name,
            pre_delete_collection=first_batch,
            use_jsonb=True,
        )
        return len(docs)
    except Exception:
        logger.exception("Writer worker failed")
        raise


def build_index_streaming(kb_dir: Path):
    """
    Main controller that:
    - spawns THREADS to run process_file_streaming(file, splitter) producers
    - collects splits into a bounded queue
    - drains queue, forming batches, and submits batches to a process pool of writers
    """

    logger.info("--- 🚀 Starting Knowledge Base Index Build (optimized) ---")

    pdfs = list(kb_dir.rglob("*.pdf"))
    mds = list(kb_dir.rglob("*.md"))
    svds = list(chain(kb_dir.rglob("*.svd"), kb_dir.rglob("*.xml")))
    dts = list(kb_dir.rglob("*.dts"))
    all_files = list(chain(pdfs, mds, svds, dts))
    if not all_files:
        logger.warning("No documents found. Exiting.")
        return
    logger.info(f"Found {len(all_files)} total documents to process.")

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    logger.info(
        f"Config: FILE_LOADER_THREADS={FILE_LOADER_THREADS}, WRITER_PROCESSES={WRITER_PROCESSES}, "
        f"EMBED_BATCH_SIZE={EMBED_BATCH_SIZE}, SPLIT_QUEUE_MAXSIZE={SPLIT_QUEUE_MAXSIZE}"
    )

    split_q: "queue.Queue[Document]" = queue.Queue(maxsize=SPLIT_QUEUE_MAXSIZE)

    producer_count = 0
    stop_event = threading.Event()

    def producer(file_path: Path):
        try:
            for split in process_file_streaming(file_path, splitter):
                split_q.put(split)
        except Exception:
            logger.exception("Producer failed for %s", file_path)
        finally:
            return file_path

    ctx = multiprocessing.get_context("spawn")
    pool = ctx.Pool(processes=WRITER_PROCESSES)

    writer_results = []

    first_batch_flag = True
    total_chunks = 0
    processed_files = 0

    with ThreadPoolExecutor(max_workers=FILE_LOADER_THREADS) as executor:
        futures = [executor.submit(producer, f) for f in all_files]
        producer_count = len(futures)
        logger.info("Submitted %d file loader tasks", producer_count)

        current_batch: List[Document] = []

        while True:
            try:
                split = split_q.get(timeout=1)
            except queue.Empty:
                if all(f.done() for f in futures) and split_q.empty():
                    break
                continue

            current_batch.append(split)
            total_chunks += 1

            if len(current_batch) >= EMBED_BATCH_SIZE:
                serialized = [{"page_content": d.page_content, "metadata": d.metadata} for d in current_batch]
                ar = pool.apply_async(
                    writer_process_worker,
                    args=(serialized, DATABASE_URL, first_batch_flag, EMBEDDING_MODEL_NAME, COLLECTION_NAME),
                )
                writer_results.append(ar)
                logger.info("Submitted batch of %d chunks to writer (first_batch=%s)", len(current_batch), first_batch_flag)
                first_batch_flag = False
                current_batch = []
                gc.collect()

            split_q.task_done()

            if total_chunks % (EMBED_BATCH_SIZE * 4) == 0:
                logger.info("Progress: produced %d chunks so far", total_chunks)

        if current_batch:
            serialized = [{"page_content": d.page_content, "metadata": d.metadata} for d in current_batch]
            ar = pool.apply_async(
                writer_process_worker,
                args=(serialized, DATABASE_URL, first_batch_flag, EMBEDDING_MODEL_NAME, COLLECTION_NAME),
            )
            writer_results.append(ar)
            logger.info("Submitted final batch of %d chunks to writer (first_batch=%s)", len(current_batch), first_batch_flag)
            first_batch_flag = False
            current_batch = []
            gc.collect()

        for f in futures:
            try:
                file_finished = f.result()  # will raise if producer crashed
                processed_files += 1
                logger.info("Finished producing splits for %s", file_finished)
            except Exception as exc:
                logger.error("File loader task raised exception: %s", exc)

    pool.close()
    pool.join()
    logger.info("All writer processes finished. Checking results...")

    written_chunks = 0
    for ar in writer_results:
        try:
            res = ar.get()
            if isinstance(res, int):
                written_chunks += res
        except Exception as exc:
            logger.error("Writer batch raised exception: %s", exc)
            raise

    logger.info("🎉 Index build complete! Processed %d files, %d produced chunks, %d written chunks (may match).",
                processed_files, total_chunks, written_chunks)


def main():
    kb_dir = Path(KNOWLEDGE_BASE_DIR)
    if not kb_dir.is_dir():
        logger.critical(f"Knowledge base directory '{KNOWLEDGE_BASE_DIR}' does not exist.")
        sys.exit(1)

    multiprocessing.set_start_method("spawn", force=True)
    build_index_streaming(kb_dir)


if __name__ == "__main__":
    main()
