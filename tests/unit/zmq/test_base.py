# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023-2026 Oxford Quantum Circuits Ltd
"""Unit tests for shared ZMQ base socket behavior."""

from unittest.mock import MagicMock, call

import pytest
import zmq

from qat_rpc.zmq._base import ZMQBase


@pytest.fixture()
def base() -> ZMQBase:
    """Create a ZMQBase with MagicMock socket and context."""
    b = object.__new__(ZMQBase)
    b._timeout = 30.0
    b._protocol = "tcp"
    b._ip_address = "127.0.0.1"
    b._port = 5556
    b._socket = MagicMock()
    b._socket.closed = False
    b._context = MagicMock()
    return b


class TestAddress:
    def test_address_property(self, base):
        assert base.address == "tcp://127.0.0.1:5556"


class TestReceive:
    def test_non_blocking_receive(self, base):
        base._socket.recv_pyobj.return_value = {"ok": True}

        result = base._receive(timeout=None)

        assert result == {"ok": True}
        base._socket.recv_pyobj.assert_called_once_with(zmq.NOBLOCK)

    def test_blocking_receive_with_timeout(self, base):
        base._socket.recv_pyobj.return_value = "result"

        result = base._receive(timeout=1.5)

        assert result == "result"
        base._socket.setsockopt.assert_called_once_with(zmq.RCVTIMEO, 1500)
        base._socket.recv_pyobj.assert_called_once_with()

    @pytest.mark.parametrize("error_code", [zmq.EAGAIN, zmq.ETERM])
    def test_error_returns_none_when_not_raising(self, base, error_code):
        base._socket.recv_pyobj.side_effect = zmq.ZMQError(error_code)

        result = base._receive(timeout=0.1, raise_on_timeout=False)

        assert result is None

    @pytest.mark.parametrize(
        ("error_code", "expected_exception"),
        [
            (zmq.EAGAIN, TimeoutError),
            (zmq.ETERM, zmq.ZMQError),
        ],
    )
    def test_error_raises_when_requested(self, base, error_code, expected_exception):
        base._socket.recv_pyobj.side_effect = zmq.ZMQError(error_code)

        with pytest.raises(expected_exception):
            base._receive(timeout=0.1, raise_on_timeout=True)


class TestSend:
    def test_send_sets_timeout_and_sends_object(self, base):
        base._send({"payload": "x"})

        base._socket.setsockopt.assert_called_once_with(zmq.SNDTIMEO, 30000)
        base._socket.send_pyobj.assert_called_once_with({"payload": "x"})

    @pytest.mark.parametrize(
        ("error_code", "expected_exception"),
        [
            (zmq.EAGAIN, TimeoutError),
            (zmq.ETERM, zmq.ZMQError),
        ],
    )
    def test_send_error_raises(self, base, error_code, expected_exception):
        base._socket.send_pyobj.side_effect = zmq.ZMQError(error_code)

        with pytest.raises(expected_exception):
            base._send("x")


class TestClose:
    def test_close_returns_if_socket_already_closed(self, base):
        base._socket.closed = True

        base.close()

        base._socket.close.assert_not_called()
        base._context.term.assert_not_called()

    def test_close_sets_linger_closes_socket_and_context(self, base):
        base.close()

        base._socket.assert_has_calls(
            [call.setsockopt(zmq.LINGER, 1000), call.close()], any_order=False
        )
        base._context.term.assert_called_once()

    def test_close_handles_eterm_from_socket_close(self, base):
        base._socket.close.side_effect = zmq.ZMQError(zmq.ETERM)

        base.close()

        base._context.term.assert_called_once()

    def test_close_handles_eterm_from_context_term(self, base):
        base._context.term.side_effect = zmq.ZMQError(zmq.ETERM)

        base.close()

        base._socket.close.assert_called_once()
