# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023-2026 Oxford Quantum Circuits Ltd
"""Backwards-compatibility shim — imports moved to ``qat_rpc.zmq.server``
and ``qat_rpc.zmq.client``.

.. deprecated:: 1.0.0
    Import ``ZMQServer`` from ``qat_rpc.zmq.server`` and ``ZMQClient``
    from ``qat_rpc.zmq.client`` instead.
"""

import warnings as _warnings

_warnings.warn(
    "Importing from 'qat_rpc.zmq.wrappers' is deprecated. "
    "Use 'qat_rpc.zmq.server' and 'qat_rpc.zmq.client' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from qat_rpc.zmq.client import ZMQClient
from qat_rpc.zmq.server import ZMQServer

__all__ = ["ZMQClient", "ZMQServer"]
