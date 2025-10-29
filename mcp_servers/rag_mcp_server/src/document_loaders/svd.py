import logging
from pathlib import Path, PurePath
from typing import Union, Iterator, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from cmsis_svd.model import (
    SVDField,
    SVDRegister,
    SVDFieldArray,
    SVDRegisterClusterArray,
    SVDRegisterArray,
    SVDRegisterCluster,
)
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

from cmsis_svd.parser import SVDParser

logger = logging.getLogger(__name__)


class SVDLoader(BaseLoader):
    """Threaded SVD loader that parses CMSIS-SVD files into LangChain documents."""

    def __init__(self, file_path: Union[str, PurePath], max_workers: int = 8) -> None:
        """
        Initialize with a path to an SVD file.

        Args:
            file_path: Path to the .svd or .xml file to load.
            max_workers: Number of threads for parallel register processing.
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"SVD file not found: {path}")
        if not path.is_file():
            raise ValueError(f"Expected a file, got directory: {path}")
        if path.suffix.lower() not in {".svd", ".xml"}:
            raise ValueError(f"Invalid file extension '{path.suffix}'. Expected .svd or .xml")

        self.file_path = str(path)
        self.max_workers = max_workers

    def load(self) -> list[Document]:
        """Load all parsed documents eagerly."""
        return list(self.lazy_load())

    def lazy_load(self) -> Iterator[Document]:
        """Safely stream parsed SVD documents lazily (device → peripheral → register)."""
        try:
            parser = SVDParser.for_xml_file(self.file_path)
            device = parser.get_device()
        except Exception as e:
            logger.exception(f"Failed to parse SVD file {self.file_path}: {e}")
            return

        # --- Device-level document ---
        yield Document(
            page_content=(
                f"Device: {device.name}\n"
                f"Vendor: {device.vendor}\n"
                f"Description: {device.description}\n"
                f"Version: {device.version}"
            ),
            metadata={
                "level": "device",
                "file_path": self.file_path,
                "device_name": device.name,
                "vendor": device.vendor,
            },
        )

        peripherals = getattr(device, "peripherals", []) or []
        if not peripherals:
            logger.warning(f"No peripherals found in {self.file_path}")
            return

        # --- Process peripherals in parallel ---
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._process_peripheral, device, p): p.name for p in peripherals
            }

            for future in as_completed(futures):
                try:
                    for doc in future.result():
                        yield doc
                except Exception as e:
                    logger.warning(
                        f"Peripheral processing failed ({futures[future]}) in {self.file_path}: {e}"
                    )

    def _process_peripheral(self, device, peripheral) -> List[Document]:
        """Process a single peripheral and its registers."""
        docs = [
            Document(
                page_content=(
                    f"Peripheral: {peripheral.name}\n"
                    f"Description: {getattr(peripheral, 'description', 'No description')}\n"
                    f"Base address: 0x{getattr(peripheral, 'base_address', 0):X}\n"
                    f"Access: {getattr(peripheral, 'access', 'N/A')}"
                ),
                metadata={
                    "level": "peripheral",
                    "file_path": self.file_path,
                    "device_name": device.name,
                    "peripheral_name": peripheral.name,
                    "base_address": getattr(peripheral, "base_address", None),
                },
            )
        ]

        registers = getattr(peripheral, "registers", None)
        if not registers:
            return docs

        # Collect register-level documents
        for doc in self._process_registers(device, peripheral, registers):
            docs.append(doc)
        return docs

    def _process_registers(
        self,
        device,
        peripheral,
        registers: List[
            Union[
                SVDRegister,
                SVDRegisterArray,
                SVDRegisterCluster,
                SVDRegisterClusterArray,
            ]
        ],
    ) -> Iterator[Document]:
        """Recursively process registers, arrays, and clusters."""
        for reg in registers:
            try:
                if isinstance(reg, SVDRegister):
                    yield from self._emit_register(device, peripheral, reg)

                elif isinstance(reg, SVDRegisterArray):
                    if reg.meta_register:
                        yield from self._emit_register(device, peripheral, reg.meta_register)
                    for r in getattr(reg, "registers", []) or []:
                        yield from self._emit_register(device, peripheral, r)

                elif isinstance(reg, SVDRegisterCluster):
                    if getattr(reg, "registers", None):
                        yield from self._process_registers(device, peripheral, reg.registers)
                    if getattr(reg, "clusters", None):
                        yield from self._process_registers(device, peripheral, reg.clusters)

                elif isinstance(reg, SVDRegisterClusterArray):
                    if reg.meta_cluster:
                        yield from self._process_registers(device, peripheral, reg.meta_cluster.registers)
                    for cluster in getattr(reg, "clusters", []) or []:
                        yield from self._process_registers(device, peripheral, cluster.registers)

                else:
                    logger.debug(f"Skipping unsupported register type {type(reg)} in {peripheral.name}")

            except Exception as e:
                logger.debug(f"Failed to process register in {peripheral.name}: {e}")

    def _emit_register(self, device, peripheral, register: SVDRegister) -> Iterator[Document]:
        """Emit a simplified register document (no field recursion)."""
        try:
            yield Document(
                page_content=(
                    f"Register: {register.name}\n"
                    f"Peripheral: {peripheral.name}\n"
                    f"Device: {device.name}\n"
                    f"Description: {getattr(register, 'description', 'No description')}\n"
                    f"Offset: 0x{getattr(register, 'address_offset', 0):X}\n"
                    f"Access: {getattr(register, 'access', 'N/A')}\n"
                    f"Reset value: {getattr(register, 'reset_value', 'Unknown')}"
                ),
                metadata={
                    "level": "register",
                    "file_path": self.file_path,
                    "device_name": device.name,
                    "vendor": getattr(device, "vendor", "Unknown"),
                    "peripheral_name": peripheral.name,
                    "register_name": register.name,
                    "address_offset": getattr(register, "address_offset", None),
                },
            )
        except Exception as e:
            logger.debug(f"Failed to emit register {getattr(register, 'name', '?')} in {peripheral.name}: {e}")

