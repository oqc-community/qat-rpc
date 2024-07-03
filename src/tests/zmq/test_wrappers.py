import threading

import pytest
from qat.purr.compiler.config import CompilerConfig

from qat_rpc.zmq.wrappers import ZMQClient, ZMQServer


@pytest.fixture(scope="module", autouse=True)
def server():
    server = ZMQServer()
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


def test_zmq_flow():
    client = ZMQClient()

    config = CompilerConfig()
    config.results_format.binary_count()
    config.repeats = 100

    response = client.execute_task(program, config)
    assert response["results"]["c"]["00"] == 100


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
