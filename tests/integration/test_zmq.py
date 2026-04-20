# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023-2026 Oxford Quantum Circuits Ltd
"""Integration tests for the ZMQ client/server round-trip."""

import threading
from importlib.metadata import version
from pathlib import Path

import pytest
from compiler_config.config import CompilerConfig

from qat_rpc.metrics import PROMETHEUS_PORT, MetricExporter, PrometheusReceiver
from qat_rpc.zmq.client import ZMQClient
from qat_rpc.zmq.server import ZMQServer

PROGRAM_DATA = Path(__file__).parent / "program_data"

QASM2_PROGRAM = """
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
h q;
creg c[2];
measure q->c;
"""

QASM3_PROGRAM = """\
OPENQASM 3;
bit[2] c;
qubit[2] q;
h q;
measure q -> c;
"""

QIR_TEXT_PROGRAM = """\
; ModuleID = 'basic'
source_filename = "basic"

%Qubit = type opaque
%Result = type opaque

define void @main() #0 {
entry:
  call void @__quantum__qis__h__body(%Qubit* inttoptr (i64 0 to %Qubit*))
  call void @__quantum__qis__h__body(%Qubit* inttoptr (i64 1 to %Qubit*))
  call void @__quantum__qis__mz__body(%Qubit* inttoptr (i64 0 to %Qubit*), %Result* inttoptr (i64 0 to %Result*))
  call void @__quantum__qis__mz__body(%Qubit* inttoptr (i64 1 to %Qubit*), %Result* inttoptr (i64 1 to %Result*))
  call void @__quantum__rt__result_record_output(%Result* inttoptr (i64 0 to %Result*), i8* null)
  call void @__quantum__rt__result_record_output(%Result* inttoptr (i64 1 to %Result*), i8* null)
  ret void
}

declare void @__quantum__qis__x__body(%Qubit*)

declare void @__quantum__qis__h__body(%Qubit*)

declare void @__quantum__qis__mz__body(%Qubit*, %Result*)

declare void @__quantum__rt__result_record_output(%Result*, i8*)

attributes #0 = { "EntryPoint" "requiredQubits"="2" "requiredResults"="2" }
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
        response = _client.execute_task(QASM2_PROGRAM, _make_config(100))
        assert response["results"]["c"]["00"] == 100

    @pytest.mark.parametrize(
        ("program", "label"),
        [
            pytest.param(QASM3_PROGRAM, "qasm3", id="qasm3"),
            pytest.param(QIR_TEXT_PROGRAM, "qir-text", id="qir-text"),
            pytest.param(
                (PROGRAM_DATA / "basic.bc").read_bytes(), "qir-binary", id="qir-binary"
            ),
        ],
    )
    def test_program_formats(self, _client, program, label):
        """All supported program formats produce a results dict."""
        response = _client.execute_task(program, _make_config(100))
        assert "results" in response, f"{label}: missing 'results' key"
        assert isinstance(response["results"], dict), f"{label}: results is not a dict"

    def test_legacy_tuple_format(self, _client):
        """Pre-1.0 tuple wire format still works end-to-end."""
        _client._send(("program", QASM2_PROGRAM, _make_config(100).to_json()))
        response = _client._await_results()
        assert response["results"]["c"]["00"] == 100

    def test_invalid_program_returns_exception(self, _client):
        """Server wraps errors in an Exception dict rather than crashing."""
        _client._send(("program", [4, 5, 6], _make_config().to_json()))
        response = _client._await_results()
        assert "Exception" in response
        assert "validation error" in response["Exception"]

    def test_concurrent_clients(self):
        """Results are routed to the correct client across threads."""
        errors = []

        def _run(repeats, expected):
            try:
                client = ZMQClient()
                response = client.execute_task(QASM2_PROGRAM, _make_config(repeats))
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

        # When testing api_version, also confirm it matches the package version
        if method_name == "api_version":
            assert result[key] == version("qat_rpc")

    def test_qubit_info_not_implemented(self, _client):
        """qubit_info is not implemented — server returns an Exception dict."""
        result = _client.qubit_info()
        assert "Exception" in result
        assert "NotImplementedError" in result["Exception"]

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
