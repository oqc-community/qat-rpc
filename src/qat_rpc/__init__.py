"""QAT-RPC: Remote Procedure Call tooling for OQC Quantum Assembly Toolchain."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("qat-rpc")
except PackageNotFoundError:
    __version__ = "unknown"

__all__ = [
    "__version__",
]
