"""Unit tests for shared ZMQ base socket behavior."""

import pytest
import zmq

from qat_rpc.zmq._base import ZMQBase


class _FakeSocket:
    def __init__(self):
        self.closed = False
        self.recv_return = None
        self.recv_exception = None
        self.send_exception = None
        self.close_exception = None
        self.setsockopt_calls = []
        self.recv_calls = []
        self.send_calls = []
        self.close_calls = 0

    def setsockopt(self, option, value):
        self.setsockopt_calls.append((option, value))

    def recv_pyobj(self, *args):
        self.recv_calls.append(args)
        if self.recv_exception is not None:
            raise self.recv_exception
        return self.recv_return

    def send_pyobj(self, obj):
        self.send_calls.append(obj)
        if self.send_exception is not None:
            raise self.send_exception

    def close(self):
        self.close_calls += 1
        if self.close_exception is not None:
            raise self.close_exception
        self.closed = True


class _FakeContext:
    def __init__(self):
        self.term_exception = None
        self.term_calls = 0

    def term(self):
        self.term_calls += 1
        if self.term_exception is not None:
            raise self.term_exception


@pytest.fixture()
def base() -> ZMQBase:
    """Create a ZMQBase with fake socket and context."""
    b = object.__new__(ZMQBase)
    b._timeout = 30.0
    b._protocol = "tcp"
    b._ip_address = "127.0.0.1"
    b._port = 5556
    b._socket = _FakeSocket()
    b._context = _FakeContext()
    return b


class TestAddress:
    def test_address_property(self, base):
        assert base.address == "tcp://127.0.0.1:5556"


class TestReceive:
    def test_non_blocking_receive(self, base):
        base._socket.recv_return = {"ok": True}

        result = base._receive(timeout=None)

        assert result == {"ok": True}
        assert base._socket.recv_calls == [(zmq.NOBLOCK,)]

    def test_blocking_receive_with_timeout(self, base):
        base._socket.recv_return = "result"

        result = base._receive(timeout=1.5)

        assert result == "result"
        assert base._socket.setsockopt_calls == [(zmq.RCVTIMEO, 1500)]
        assert base._socket.recv_calls == [()]

    @pytest.mark.parametrize("error_code", [zmq.EAGAIN, zmq.ETERM])
    def test_error_returns_none_when_not_raising(self, base, error_code):
        base._socket.recv_exception = zmq.ZMQError(error_code)

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
        base._socket.recv_exception = zmq.ZMQError(error_code)

        with pytest.raises(expected_exception):
            base._receive(timeout=0.1, raise_on_timeout=True)


class TestSend:
    def test_send_sets_timeout_and_sends_object(self, base):
        base._send({"payload": "x"})

        assert base._socket.setsockopt_calls == [(zmq.SNDTIMEO, 30000)]
        assert base._socket.send_calls == [{"payload": "x"}]

    @pytest.mark.parametrize(
        ("error_code", "expected_exception"),
        [
            (zmq.EAGAIN, TimeoutError),
            (zmq.ETERM, zmq.ZMQError),
        ],
    )
    def test_send_error_raises(self, base, error_code, expected_exception):
        base._socket.send_exception = zmq.ZMQError(error_code)

        with pytest.raises(expected_exception):
            base._send("x")


class TestClose:
    def test_close_returns_if_socket_already_closed(self, base):
        base._socket.closed = True

        base.close()

        assert base._socket.close_calls == 0
        assert base._context.term_calls == 0

    def test_close_sets_linger_closes_socket_and_context(self, base):
        base.close()

        assert base._socket.setsockopt_calls == [(zmq.LINGER, 1000)]
        assert base._socket.close_calls == 1
        assert base._context.term_calls == 1

    def test_close_handles_eterm_from_socket_close(self, base):
        base._socket.close_exception = zmq.ZMQError(zmq.ETERM)

        base.close()

        assert base._context.term_calls == 1

    def test_close_handles_eterm_from_context_term(self, base):
        base._context.term_exception = zmq.ZMQError(zmq.ETERM)

        base.close()

        assert base._socket.close_calls == 1
