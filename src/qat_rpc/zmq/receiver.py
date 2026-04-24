# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023-2026 Oxford Quantum Circuits Ltd
"""Backwards-compatibility shim — imports moved to ``qat_rpc.zmq.server``.

.. deprecated:: 1.0.0
    Use the ``qat_server`` console script to start the server, or import
    from ``qat_rpc.zmq.server`` directly.
"""

import warnings as _warnings

_warnings.warn(
    "Importing from 'qat_rpc.zmq.receiver' is deprecated. "
    "Use 'qat_rpc.zmq.server' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from qat_rpc.zmq.server import (
    RECEIVER_PORT,
    GracefulKill,
    main,
    resolve_qat_config_path,
    validate_port,
)

__all__ = [
    "RECEIVER_PORT",
    "GracefulKill",
    "main",
    "resolve_qat_config_path",
    "validate_port",
]
