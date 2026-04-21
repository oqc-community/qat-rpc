# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023-2026 Oxford Quantum Circuits Ltd
"""Backwards-compatibility shim — imports moved to ``qat_rpc.zmq.client_cli``.

.. deprecated:: 1.0.0
    Import from ``qat_rpc.zmq.client_cli`` instead.
"""

import warnings as _warnings

_warnings.warn(
    "Importing from 'qat_rpc.zmq.qat_commands' is deprecated. "
    "Use 'qat_rpc.zmq.client_cli' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from qat_rpc.zmq.client_cli import qat_run

__all__ = ["qat_run"]
