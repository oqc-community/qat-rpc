"""Integration tests for the ZMQ client/server round-trip."""

import threading
from importlib.metadata import version

import pytest
from compiler_config.config import CompilerConfig

from qat_rpc.metrics import PROMETHEUS_PORT, MetricExporter, PrometheusReceiver
from qat_rpc.zmq.client import ZMQClient
from qat_rpc.zmq.server import ZMQServer

PROGRAM = """
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
h q;
creg c[2];
measure q->c;
"""


@pytest.fixture(scope="module", autouse=True)
def _server():
    """Start a real ZMQServer in a daemon thread for the module."""
    server = ZMQServer(
        metric_exporter=MetricExporter(backend=PrometheusReceiver(PROMETHEUS_PORT)),
    )
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()
    yield
    server.stop()


@pytest.fixture()
def _client() -> ZMQClient:
    return ZMQClient()


def _make_config(repeats: int = 100) -> CompilerConfig:
    config = CompilerConfig()
    config.results_format.binary_count()
    config.repeats = repeats
    return config


class TestExecuteRoundTrip:
    def test_execute_task(self, _client):
        response = _client.execute_task(PROGRAM, _make_config(100))
        assert response["results"]["c"]["00"] == 100

    def test_legacy_tuple_format(self, _client):
        """Pre-1.0 tuple wire format still works end-to-end."""
        _client._send(("program", PROGRAM, _make_config(100).to_json()))
        response = _client._await_results()
        assert response["results"]["c"]["00"] == 100

    def test_invalid_program_returns_exception(self, _client):
        """Server wraps errors in an Exception dict rather than crashing."""
        _client._send(("program", [4, 5, 6], _make_config().to_json()))
        response = _client._await_results()
        assert "Exception" in response

    def test_concurrent_clients(self):
        """Results are routed to the correct client across threads."""
        errors = []

        def _run(repeats, expected):
            try:
                client = ZMQClient()
                response = client.execute_task(PROGRAM, _make_config(repeats))
                assert response["results"] == expected
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=_run, args=(100, {"c": {"00": 100}})),
            threading.Thread(target=_run, args=(100, {"c": {"00": 100}})),
            threading.Thread(target=_run, args=(1000, {"c": {"00": 1000}})),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread failures: {errors}"


class TestMetadataQueries:
    @pytest.mark.parametrize(
        ("method_name", "key", "expected_type"),
        [
            ("api_version", "qat_rpc_version", str),
            ("qpu_couplings", "couplings", list),
            ("qpu_info", "qpu_info", dict),
        ],
    )
    def test_metadata_queries(self, _client, method_name, key, expected_type):
        result = getattr(_client, method_name)()
        assert key in result
        assert isinstance(result[key], expected_type)
        if method_name == "api_version":
            assert result[key] == version("qat_rpc")

    def test_qubit_info_not_implemented(self, _client):
        """qubit_info is not implemented — server returns an Exception dict."""
        result = _client.qubit_info()
        assert "Exception" in result

    def test_compile_pipelines(self, _client):
        result = _client.compile_pipelines()
        assert "compile_pipelines" in result
        assert isinstance(result["compile_pipelines"], list)
        assert "default" in result
        assert isinstance(result["default"], str)

    def test_execute_pipelines(self, _client):
        result = _client.execute_pipelines()
        assert "execute_pipelines" in result
        assert isinstance(result["execute_pipelines"], list)
        assert "default" in result
        assert isinstance(result["default"], str)
