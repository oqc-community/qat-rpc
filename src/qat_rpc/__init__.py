# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023-2026 Oxford Quantum Circuits Ltd
"""QAT-RPC: Remote Procedure Call tooling for OQC Quantum Assembly Toolchain."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("qat-rpc")
except PackageNotFoundError:
    __version__ = "unknown"

__all__ = [
    "__version__",
]
