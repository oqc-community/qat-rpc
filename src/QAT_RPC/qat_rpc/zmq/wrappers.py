from enum import Enum
from importlib.metadata import version
from time import time
from typing import Optional, Union

import zmq
from compiler_config.config import CompilerConfig
from qat.purr.backends.echo import get_default_echo_hardware
from qat.purr.compiler.hardware_models import QuantumHardwareModel
from qat.purr.compiler.runtime import get_runtime
from qat.purr.integrations.features import OpenPulseFeatures
from qat.qat import execute_with_metrics

from qat_rpc.utils.metrics import MetricExporter


class Messages(Enum):
    PROGRAM = "program"
    VERSION = "version"
    COUPLINGS = "couplings"
    QUBIT_INFO = "qubit_info"
    QPU_INFO = "qpu_info"


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
            except zmq.ZMQError:
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
    def __init__(
        self,
        hardware: Optional[QuantumHardwareModel] = None,
        metric_exporter: Optional[MetricExporter] = None,
    ):
        super().__init__(zmq.REP)
        self._metric = metric_exporter
        self._socket.bind(self.address)
        self._hardware = hardware or get_default_echo_hardware(qubit_count=32)
        self._engine = get_runtime(self._hardware).engine
        self._running = False

    @property
    def address(self):
        return f"{self._protocol}://*:{self._port}"

    def _program(self, program, config):
        program = program
        config = CompilerConfig.create_from_json(config)
        result, metrics = execute_with_metrics(program, self._engine, config)
        return {"results": result, "execution_metrics": metrics}

    def _version(self):
        return {"qat_rpc_version": str(version("qat_rpc"))}

    def _couplings(self):
        coupling = [
            coupled.direction for coupled in self._hardware.qubit_direction_couplings
        ]
        return {"couplings": coupling}

    def _qubit_info(self):
        raise NotImplementedError(
            "Individual qubit information not implented, pending hardware model changes."
        )

    def _qpu_info(self):
        features = OpenPulseFeatures()
        features.for_hardware(self._hardware)
        qpu_info = features.to_json_dict()
        return {"qpu_info": qpu_info}

    def _interpret_message(self, message):
        match message[0]:
            case Messages.PROGRAM.value:
                print(message)
                if len(message) != 3:
                    raise ValueError(
                        f"Program message should be of length 3, not {len(message)}"
                    )
                return self._program(message[1], message[2])
            case Messages.VERSION.value:
                return self._version()
            case Messages.COUPLINGS.value:
                return self._couplings()
            case Messages.QUBIT_INFO:
                return self._qubit_info()
            case Messages.QPU_INFO.value:
                return self._qpu_info()

            case _:
                return self._program(message[0], message[1])

    def run(self):
        self._running = True
        with self._metric.receiver_status() as metric:
            metric.succeed()
        while self._running and not self._socket.closed:
            msg = self._check_recieved()
            if msg is not None:
                try:
                    reply = self._interpret_message(message=msg)
                    with self._metric.executed_messages() as executed:
                        executed.increment()
                except Exception as e:
                    reply = {"Exception": repr(e)}
                    with self._metric.failed_messages() as failed:
                        failed.increment()
                self._send(reply)

    def stop(self):
        self._running = False
        with self._metric.receiver_status() as metric:
            metric.fail()


class ZMQClient(ZMQBase):
    def __init__(self):
        super().__init__(zmq.REQ)
        self._socket.setsockopt(zmq.LINGER, 0)
        self._socket.connect(self.address)

    def _send(self, message):
        super()._send(message=message)
        return self._await_results()

    def _await_results(self):
        result = None
        while result is None:
            result = self._check_recieved()
        return result

    def execute_task(self, program: str, config: Union[CompilerConfig, str] = None):
        self.result = None
        if isinstance(config, str):
            # Verify config string is valid before submitting.
            config = CompilerConfig.create_from_json(config)
        cfg = config or CompilerConfig()
        return self._send((Messages.PROGRAM.value, program, cfg.to_json()))

    def api_version(self):
        return self._send((Messages.VERSION.value,))

    def qpu_couplings(self):
        return self._send((Messages.COUPLINGS.value,))

    def qubit_info(self):
        return self._send((Messages.QUBIT_INFO.value,))

    def qpu_info(self):
        return self._send((Messages.QPU_INFO.value,))
