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
    """Memory-efficient SVD loader that streams Documents as generators."""

    def __init__(self, file_path: Union[str, PurePath], max_workers: int = 4) -> None:
        """
        Initialize with a path to an SVD file.

        Args:
            file_path: Path to the .svd or .xml file to load.
            max_workers: Number of threads for parallel peripheral processing.
                         Keep modest to avoid peak memory blow-up.
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
        """Eager convenience wrapper (not recommended for very large SVDs)."""
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
            page_content="\n".join(
                [
                    f"Device: {device.name}",
                    f"Vendor: {device.vendor}",
                    f"Description: {device.description}",
                    f"Version: {device.version}",
                ]
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
            try:
                del device
                del parser
            except Exception:
                pass
            return

        base_meta = {"file_path": self.file_path, "device_name": device.name}

        if self.max_workers and self.max_workers > 1:
            logger.debug(f"Processing peripherals in parallel (max_workers={self.max_workers})...")
            # --- Process peripherals in parallel ---
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self._process_peripheral, device, p, base_meta): p.name
                    for p in peripherals
                }

                # Release main thread's device object
                try:
                    del device
                    del peripherals
                    del parser
                except Exception:
                    pass

                for future in as_completed(futures):
                    peripheral_name = futures[future]
                    try:
                        gen = future.result()
                        if gen is None:
                            continue
                        for doc in gen:
                            yield doc
                    except Exception as e:
                        logger.warning(
                            f"Peripheral processing failed ({peripheral_name}) in {self.file_path}: {e}"
                        )
        else:
            logger.debug("Processing peripherals serially...")
            # --- Process peripherals serially ---
            for p in peripherals:
                try:
                    gen = self._process_peripheral(device, p, base_meta)
                    if gen is None:
                        continue
                    for doc in gen:
                        yield doc
                except Exception as e:
                    logger.warning(
                        f"Peripheral processing failed ({p.name}) in {self.file_path}: {e}"
                    )

            # Release main thread's device object
            try:
                del device
                del peripherals
                del parser
            except Exception:
                pass

    def _process_peripheral(self, device, peripheral, base_meta) -> Iterator[Document]:
        """
        Lazily process a single peripheral and its registers.
        Returns a generator that yields Document objects.
        """
        try:
            # peripheral-level doc
            yield Document(
                page_content="\n".join(
                    [
                        f"Peripheral: {peripheral.name}",
                        f"Description: {getattr(peripheral, 'description', 'No description')}",
                        f"Base address: 0x{getattr(peripheral, 'base_address', 0):X}",
                        f"Access: {getattr(peripheral, 'access', 'N/A')}",
                    ]
                ),
                metadata={
                    **base_meta,
                    "level": "peripheral",
                    "peripheral_name": peripheral.name,
                    "base_address": getattr(peripheral, "base_address", None),
                },
            )
        except Exception as e:
            logger.debug(f"Failed to emit peripheral doc for {getattr(peripheral, 'name', '?')}: {e}")
            return

        registers = getattr(peripheral, "registers", None)
        if not registers:
            return

        try:
            yield from self._process_registers(device, peripheral, registers, base_meta)
        finally:
            try:
                del registers
            except Exception:
                pass

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
        base_meta,
    ) -> Iterator[Document]:
        """Recursively process registers, arrays, and clusters, streaming Documents."""
        for reg in registers:
            try:
                # direct register
                if isinstance(reg, SVDRegister):
                    yield from self._emit_register(device, peripheral, reg, base_meta)

                # register array: emit meta_register if present + each element
                elif isinstance(reg, SVDRegisterArray):
                    if reg.meta_register:
                        yield from self._emit_register(device, peripheral, reg.meta_register, base_meta)
                    for r in getattr(reg, "registers", []) or []:
                        yield from self._emit_register(device, peripheral, r, base_meta)

                # cluster with nested registers/clusters
                elif isinstance(reg, SVDRegisterCluster):
                    if getattr(reg, "registers", None):
                        yield from self._process_registers(device, peripheral, reg.registers, base_meta)
                    if getattr(reg, "clusters", None):
                        yield from self._process_registers(device, peripheral, reg.clusters, base_meta)

                # cluster array: process meta_cluster + clusters
                elif isinstance(reg, SVDRegisterClusterArray):
                    if reg.meta_cluster:
                        # meta_cluster may have registers
                        yield from self._process_registers(
                            device, peripheral, reg.meta_cluster.registers or [], base_meta
                        )
                    for cluster in getattr(reg, "clusters", []) or []:
                        yield from self._process_registers(device, peripheral, cluster.registers or [], base_meta)

                else:
                    logger.debug(f"Skipping unsupported register type {type(reg)} in {peripheral.name}")

            except Exception as e:
                logger.debug(f"Failed to process register in {peripheral.name}: {e}")

    def _emit_register(self, device, peripheral, register: SVDRegister, base_meta) -> Iterator[Document]:
        """Emit a simplified register document (no field recursion), streaming a single Document."""
        try:
            page_content = "\n".join(
                [
                    f"Register: {register.name}",
                    f"Peripheral: {peripheral.name}",
                    f"Device: {device.name}",
                    f"Description: {getattr(register, 'description', 'No description')}",
                    f"Offset: 0x{getattr(register, 'address_offset', 0):X}",
                    f"Access: {getattr(register, 'access', 'N/A')}",
                    f"Reset value: {getattr(register, 'reset_value', 'Unknown')}",
                ]
            )

            meta = {
                **base_meta,
                "level": "register",
                "vendor": getattr(device, "vendor", "Unknown"),
                "peripheral_name": peripheral.name,
                "register_name": register.name,
                "address_offset": getattr(register, "address_offset", None),
            }

            yield Document(page_content=page_content, metadata=meta)

        except Exception as e:
            logger.debug(f"Failed to emit register {getattr(register, 'name', '?')} in {peripheral.name}: {e}")
            return
