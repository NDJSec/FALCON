import logging
from pathlib import Path, PurePath
from typing import Union, Iterator, Any

from devicetree import dtlib
from devicetree.dtlib import DT, Node

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

class DTSLoader(BaseLoader):
    def __init__(self, file_path: Union[str, PurePath]) -> None:
        """
        Initialize with a path to a DTS file.

        Args:
            file_path: Path to the .dts file to load.
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"DTS file not found: {path}")
        if not path.is_file():
            raise ValueError(f"Expected a file, got directory: {path}")
        if path.suffix.lower() not in {".dts"}:
            raise ValueError(f"Invalid file extension '{path.suffix}'. Expected .dts")

        self.file_path = str(path)

    def load(self) -> list[Document]:
        """Eager convenience wrapper (not recommended for very large DTSs)."""
        return list(self.lazy_load())

    def lazy_load(self) -> Iterator[Document]:
        """Safely stream parsed DTS documents lazily"""
        try:
            dt = DT(self.file_path)
        except Exception as e:
            logger.exception(f"Failed to parse DTS file {self.file_path}: {e}")
            return

        for node in self._walk_nodes(dt.root):
            yield self._node_to_document(node)

    def _walk_nodes(self, node: Node) -> Iterator[Node]:
        """Recursive generator over all nodes."""
        yield node
        for _, child in node.nodes:
            yield from self._walk_nodes(child)

    def _node_to_document(self, node: Node) -> Document:
        """Convert a devicetree node into a human-readable RAG document."""

        lines = [
            f"Node path: {node.path}",
        ]

        # Node labels (dt-level identifiers)
        if node.labels:
            lines.append(f"Node labels: {', '.join(node.labels)}")

        # "label" property inside node
        if "label" in node.props:
            label_prop = dtlib.to_string(node.props["label"].value)
            lines.append(f'Device label property: "{label_prop}"')

        # Standard properties
        if node.props:
            lines.append("\nProperties:")
            for name, prop in node.props.items():
                value = self._format_value(prop.value)
                lines.append(f"  {name} = {value}")

        page_content = "\n".join(lines)

        # Metadata for RAG retrieval
        metadata = {
            "path": node.path,
            "node_labels": node.labels.copy(),  # devicetree labels
            "label_property": dtlib.to_string(node.props["label"].value)
            if "label" in node.props else None,
            "compatible": self._extract_prop(node, "compatible"),
            "reg": self._extract_prop(node, "reg"),
            "interrupts": self._extract_prop(node, "interrupts"),
            "file": self.file_path,
        }

        return Document(page_content=page_content, metadata=metadata)

    def _extract_prop(self, node: Node, name: str):
        """Extract a node property for metadata (safe)."""
        prop = node.props.get(name)
        if not prop:
            return None
        return self._format_value(prop.value)

    def _format_value(self, val: Any) -> Any:
        """Turn dtlib property values into readable Python types."""
        if isinstance(val, bytes):
            return val.hex()
        if isinstance(val, list):
            return [self._format_value(v) for v in val]
        return val
