import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from svd import SVDLoader

_module_lookup = {
    "SVDLoader": "document_loaders.svd",
}

def __getattr__(name: str) -> Any:
    if name in _module_lookup:
        module = importlib.import_module(_module_lookup[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__} has no attribute {name}")

__all__ = [
    "SVDLoader",
]
