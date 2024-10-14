import threading
from importlib.metadata import version

import pytest
from qat.purr.backends.echo import (
    add_direction_couplings_to_hardware,
    get_default_echo_hardware,
)
from qat.purr.compiler.config import CompilerConfig

from qat_rpc.utils.constants import PROMETHEUS_PORT
from qat_rpc.utils.metrics import MetricExporter, PrometheusReceiver
from qat_rpc.zmq.wrappers import ZMQClient, ZMQServer

qubit_count = 8
qpu_couplings = [(i, j) for i in range(qubit_count) for j in range(qubit_count)]


@pytest.fixture(scope="module", autouse=True)
def server():
    hardware = get_default_echo_hardware(qubit_count=qubit_count)
    hardware = add_direction_couplings_to_hardware(hardware, qpu_couplings)
    # server = ZMQServer()
    server = ZMQServer(
        hardware=hardware,
        metric_exporter=MetricExporter(backend=PrometheusReceiver(PROMETHEUS_PORT)),
    )
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()


program = """
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
h q;
creg c[2];
measure q->c;
"""


def test_zmq_exception():
    client = ZMQClient()

    config = CompilerConfig()
    config.results_format.binary_count()
    config.repeats = 100

    response = client.execute_task([4, 5, 6], config)
    assert response["Exception"] == "TypeError('expected string or buffer')"


def execute_and_check_result(client, program, config, result):
    response = client.execute_task(program, config)
    assert response["results"] == result


@pytest.mark.filterwarnings("error::pytest.PytestUnhandledThreadExceptionWarning")
def test_two_zmq_clients():
    """Verify the results are returned to the correct client."""
    client0 = ZMQClient()
    client1 = ZMQClient()

    config0 = CompilerConfig()
    config0.results_format.binary_count()
    config0.repeats = 100
    thread00 = threading.Thread(
        target=execute_and_check_result,
        args=(client0, program, config0, {"c": {"00": 100}}),
    )
    thread01 = threading.Thread(
        target=execute_and_check_result,
        args=(client0, program, config0, {"c": {"00": 100}}),
    )
    config1 = CompilerConfig()
    config1.results_format.binary_count()
    config1.repeats = 1000
    thread10 = threading.Thread(
        target=execute_and_check_result,
        args=(client1, program, config1, {"c": {"00": 1000}}),
    )
    thread00.start()
    thread01.start()
    thread10.start()
    thread00.join()
    thread01.join()
    thread10.join()


def test_program():
    client = ZMQClient()

    config = CompilerConfig()
    config.results_format.binary_count()
    config.repeats = 100

    response = client.execute_task(program, config)
    assert response["results"]["c"]["00"] == 100


def test_program_backwards_compatible():
    client = ZMQClient()

    config = CompilerConfig()
    config.results_format.binary_count()
    config.repeats = 100

    response = client._send((program, config.to_json()))
    print(response)
    assert response["results"]["c"]["00"] == 100


def test_api_version():
    client = ZMQClient()
    api_version = client.api_version()
    assert api_version["qat_rpc_version"] == version("qat_rpc")


def test_couplings():
    client = ZMQClient()
    couplings = client.qpu_couplings()
    assert couplings["couplings"] == qpu_couplings


def test_qubit_info():
    client = ZMQClient()
    qubit_info = client.qubit_info()
    assert qubit_info["Exception"] is not None


def test_qpu_info():
    client = ZMQClient()
    qpu_info = client.qpu_info()
    assert qpu_info["qpu_info"] is not None
