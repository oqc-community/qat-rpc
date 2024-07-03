from time import time
from typing import Union

import zmq

from qat.purr.backends.echo import get_default_echo_hardware
from qat.purr.compiler.hardware_models import QuantumHardwareModel
from qat.purr.compiler.config import CompilerConfig
from qat.purr.compiler.runtime import get_runtime
from qat.qat import execute_with_metrics


class ZMQBase:
    def __init__(self, socket_type: zmq.SocketType):
        self._context = zmq.Context()
        self._socket = self._context.socket(socket_type)
        self._timeout = 30.0
        self._protocol = "tcp"
        self._ip_address = "127.0.0.1"
        self._port = "5556"

    @property
    def address(self):
        return f"{self._protocol}://{self._ip_address}:{self._port}"

    def _check_recieved(self):
        try:
            msg = self._socket.recv_pyobj(zmq.NOBLOCK)
            return msg
        except zmq.ZMQError:
            return None

    def _send(self, message) -> None:
        sent = False
        t0 = time()
        while not sent:
            try:
                self._socket.send_pyobj(message, zmq.NOBLOCK)
                sent = True
            except zmq.ZMQError as e:
                if time() > t0 + self._timeout:
                    raise TimeoutError(
                        "Sending %s on %s timedout" % (message, self.address)
                    )
        return

    def close(self):
        """Disconnect the link to the socket."""
        if self._socket.closed:
            return
        self._socket.close()
        self._context.destroy()

    def __del__(self):
        self.close()


class ZMQServer(ZMQBase):
    def __init__(self, hardware: QuantumHardwareModel=None):
        super().__init__(zmq.REP)
        self._socket.bind(self.address)
        self._hardware = hardware or get_default_echo_hardware(qubit_count=32)
        self._engine = get_runtime(self._hardware).engine
        self._running = False

    @property
    def address(self):
        return f"{self._protocol}://*:{self._port}"

    def run(self):
        self._running = True
        while self._running and not self._socket.closed:
            msg = self._check_recieved()
            if msg is not None:
                try:
                    program = msg[0]
                    config = CompilerConfig.create_from_json(msg[1])
                    result, metrics = execute_with_metrics(program, self._engine, config)
                    reply = {"results": result, "execution_metrics": metrics}
                except Exception as e:
                    reply = {"Exception": repr(e)}
                self._send(reply)

    def stop(self):
        self._running = False


class ZMQClient(ZMQBase):
    def __init__(self):
        super().__init__(zmq.REQ)
        self._socket.setsockopt(zmq.LINGER, 0)
        self._socket.connect(self.address)

    def execute_task(self, program: str, config: Union[CompilerConfig, str]=None):
        self.result = None
        if isinstance(config, str):
            # Verify config string is valid before submitting.
            config = CompilerConfig.create_from_json(config)
        cfg = config or CompilerConfig()
        self._send((program, cfg.to_json()))
        return self._await_results()

    def _await_results(self):
        result = None
        while result is None:
            result = self._check_recieved()
        return result
