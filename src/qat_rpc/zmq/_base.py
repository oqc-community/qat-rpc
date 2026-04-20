# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023-2026 Oxford Quantum Circuits Ltd
"""Shared ZMQ socket base class."""

from typing import Any

import zmq
from qat.purr.utils.logger import get_default_logger

log = get_default_logger()


class ZMQBase:
    """Base class for ZMQ socket wrappers.

    Manages context/socket lifecycle, provides send/receive with timeouts,
    and handles ``EAGAIN``/``ETERM`` errors uniformly.
    """

    def __init__(
        self,
        socket_type: int,
        ip_address: str = "127.0.0.1",
        port: int = 5556,
        timeout: float = 30.0,
    ):
        self._context = zmq.Context()
        self._socket = self._context.socket(socket_type)
        self._timeout = timeout
        self._protocol = "tcp"
        self._ip_address = ip_address
        self._port = port

    @property
    def address(self) -> str:
        return f"{self._protocol}://{self._ip_address}:{self._port}"

    def _receive(self, timeout: float | None = None) -> Any:
        """Receive a pickled object from the socket.

        When *timeout* is ``None`` the call is non-blocking (``NOBLOCK``);
        ``EAGAIN`` and ``ETERM`` errors return ``None`` silently, which is
        the expected behaviour for a server polling loop.

        When *timeout* is a float the call blocks for up to that many
        seconds.  ``EAGAIN`` raises ``TimeoutError``; ``ETERM`` re-raises
        the underlying ``ZMQError``.
        """
        try:
            if timeout is None:
                msg = self._socket.recv_pyobj(zmq.NOBLOCK)
            else:
                self._socket.setsockopt(zmq.RCVTIMEO, int(timeout * 1000))
                msg = self._socket.recv_pyobj()
        except zmq.ZMQError as e:
            if e.errno == zmq.EAGAIN:
                if timeout is not None:
                    raise TimeoutError(
                        f"Receiving from {self.address} timed out after {timeout} seconds."
                    )
                return None

            if e.errno == zmq.ETERM:
                if timeout is not None:
                    raise
                log.info("Context terminated, shutting down socket.")
                return None

            raise
        else:
            return msg

    def _send(self, obj: Any) -> None:
        """Send a pickled object with a send timeout."""
        try:
            self._socket.setsockopt(zmq.SNDTIMEO, int(self._timeout * 1000))
            self._socket.send_pyobj(obj)
        except zmq.ZMQError as e:
            if e.errno == zmq.EAGAIN:
                raise TimeoutError(
                    f"Sending on {self.address} timed out after {self._timeout} seconds."
                )

            if e.errno == zmq.ETERM:
                log.info("Context terminated, cannot send message.")

            raise

    def close(self) -> None:
        """Close the socket and terminate the ZMQ context."""
        if not hasattr(self, "_socket") or self._socket.closed:
            return
        try:
            self._socket.setsockopt(zmq.LINGER, 1000)
            self._socket.close()
        except zmq.ZMQError as e:
            if e.errno == zmq.ETERM:
                log.warning(f"Error closing socket: {e}, context already terminated.")

        try:
            self._context.term()
        except zmq.ZMQError as e:
            if e.errno == zmq.ETERM:
                log.warning(f"Error terminating context: {e}, context already terminated.")
