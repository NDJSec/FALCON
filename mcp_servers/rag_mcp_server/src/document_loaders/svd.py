import logging
from pathlib import PurePath, Path
from typing import Union, Iterator

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

from .cmis_svd.parser import SVDParser

logger = logging.getLogger(__name__)

class SVDLoader(BaseLoader):
    def __init__(
        self,
        file_path: Union[str, PurePath],
    ) -> None:

        """Initialize with a file path.

        Args:
            file_path: The path to the directory of SVDs to load.

        Returns:
            This method does not directly return data. Use the `load`, `lazy_load` or
            `aload` methods to retrieve parsed documents with content and metadata.
        """
        self.file_path = str(file_path)

    def load(self) -> list[Document]:
        return list(self.lazy_load())


    def lazy_load(self) -> Iterator[Document]:
        try:
            parser = SVDParser.for_xml_file(self.file_path)
            device = parser.get_device()
        except Exception as e:
            logger.error(f"Failed to parse SVD file {self.file_path}: {e}")
            return

        # Device-level document
        yield Document(
            page_content=(
                f"Device: {device.name}\nVendor: {device.vendor}\n"
                f"Description: {device.description}\nVersion: {device.version}"
            ),
            metadata={
                "type": "device",
                "file_path": self.file_path,
                "device_name": device.name,
                "vendor": device.vendor,
            },
        )

        """
        # Peripheral and register-level documents
        for p in device.peripherals:
            yield Document(
                page_content=(
                    f"Peripheral: {p.name}\n"
                    f"Description: {p.description}\n"
                    f"Base address: 0x{p.base_address:X}\n"
                    f"Access: {p.access or 'N/A'}"
                ),
                metadata={
                    "type": "peripheral",
                    "file_path": self.file_path,
                    "device_name": device.name,
                    "peripheral": p.name,
                    "base_address": p.base_address,
                },
            )

            if p.registers:
                for r in p.registers:
                    field_lines = []
                    if r.fields:
                        for f in r.fields:
                            field_lines.append(
                                f"- {f.name}: {f.description or 'No description'} "
                                f"(bits {f.bit_offset}:{f.bit_offset + f.bit_width - 1})"
                            )

                    yield Document(
                        page_content=(
                                f"Register: {r.name}\n"
                                f"Description: {r.description or 'No description'}\n"
                                f"Offset: 0x{r.address_offset:X}\n"
                                f"Access: {r.access or 'N/A'}\n"
                                f"Reset: {r.reset_value}\n\n"
                                f"Fields:\n" + "\n".join(field_lines)
                        ),
                        metadata={
                            "type": "register",
                            "file_path": self.file_path,
                            "device_name": device.name,
                            "peripheral": p.name,
                            "register": r.name,
                            "address_offset": r.address_offset,
                        },
                    )
        """
