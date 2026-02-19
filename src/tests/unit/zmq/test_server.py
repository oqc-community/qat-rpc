"""Unit tests for ZMQ server static and pure functions."""

from signal import SIGINT, SIGTERM, getsignal

import pytest
from compiler_config.config import CompilerConfig
from pydantic import BaseModel

from qat_rpc.models import (
    CouplingsMessage,
    ProgramMessage,
    QpuInfoMessage,
    QubitInfoMessage,
    VersionMessage,
)
from qat_rpc.zmq.server import (
    GracefulKill,
    ZMQServer,
    resolve_qat_config_path,
    validate_port,
)


class TestConvertLegacyMessage:
    def test_pre_030_two_tuple(self):
        """Pre-0.3.0 format: (program_str, config_str) without type tag."""
        config = CompilerConfig().to_json()
        msg = ZMQServer._convert_legacy_message(("OPENQASM 2.0;", config))
        assert isinstance(msg, ProgramMessage)
        assert msg.program == "OPENQASM 2.0;"
        assert msg.config == config

    def test_tagged_program(self):
        """0.3.0 -> 0.6.0 format: ("program", code, config)."""
        config = CompilerConfig().to_json()
        msg = ZMQServer._convert_legacy_message(("program", "OPENQASM 2.0;", config))
        assert isinstance(msg, ProgramMessage)
        assert msg.program == "OPENQASM 2.0;"

    def test_tagged_program_with_pipelines(self):
        config = CompilerConfig().to_json()
        msg = ZMQServer._convert_legacy_message(
            ("program", "OPENQASM 2.0;", config, "compile_pipe", "exec_pipe")
        )
        assert isinstance(msg, ProgramMessage)
        assert msg.compile_pipeline == "compile_pipe"
        assert msg.execute_pipeline == "exec_pipe"

    def test_tagged_program_empty_pipelines_become_none(self):
        config = CompilerConfig().to_json()
        msg = ZMQServer._convert_legacy_message(
            ("program", "OPENQASM 2.0;", config, "", "")
        )
        assert isinstance(msg, ProgramMessage)
        assert msg.compile_pipeline is None
        assert msg.execute_pipeline is None

    @pytest.mark.parametrize(
        ("raw", "expected_cls"),
        [
            (("version",), VersionMessage),
            (("couplings",), CouplingsMessage),
            (("qubit_info",), QubitInfoMessage),
            (("qpu_info",), QpuInfoMessage),
        ],
    )
    def test_tagged_metadata_messages(self, raw, expected_cls):
        msg = ZMQServer._convert_legacy_message(raw)
        assert isinstance(msg, expected_cls)

    def test_empty_tuple_raises(self):
        with pytest.raises(ValueError, match="Invalid legacy message"):
            ZMQServer._convert_legacy_message(())

    def test_non_string_tag_raises(self):
        with pytest.raises(TypeError, match="Invalid legacy message"):
            ZMQServer._convert_legacy_message((123, "arg1", "arg2"))

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unrecognized legacy message type"):
            ZMQServer._convert_legacy_message(("unknown_op",))

    def test_program_wrong_arg_count_raises(self):
        with pytest.raises(ValueError, match="expects 2 or 4 args"):
            ZMQServer._convert_legacy_message(("program", "only_one"))


class TestSerializeResponse:
    def test_dict_passthrough(self):
        d = {"qat_rpc_version": "0.6.0"}
        assert ZMQServer._serialize_response(d) == d

    def test_pydantic_model_dump(self):
        """Pydantic response models are converted to dicts."""

        class _FakeResponse(BaseModel):
            value: str

        resp = _FakeResponse(value="hello")
        result = ZMQServer._serialize_response(resp)
        assert result == {"value": "hello"}
        assert isinstance(result, dict)


class TestValidatePort:
    def test_none_returns_default(self):
        assert validate_port(None, "test", 5556) == 5556

    @pytest.mark.parametrize(
        ("port_value", "expected"),
        [
            ("8080", 8080),
            ("abc", 5556),
            ("80", 5556),
            ("65000", 5556),
            ("1024", 5556),
            ("49152", 5556),
            ("1025", 1025),
            ("49151", 49151),
        ],
    )
    def test_port_validation_cases(self, port_value, expected):
        assert validate_port(port_value, "test", 5556) == expected

    def test_excluded_port_returns_default(self):
        assert validate_port("8080", "test", 5556, excluded_port=8080) == 5556

    def test_non_excluded_port_accepted(self):
        assert validate_port("8080", "test", 5556, excluded_port=9090) == 8080


class TestResolveQatConfigPath:
    def test_none_returns_none(self):
        assert resolve_qat_config_path(None) is None

    def test_nonexistent_file_raises(self, tmp_path):
        with pytest.raises(ValueError, match="QAT config file not found"):
            resolve_qat_config_path(str(tmp_path / "nonexistent.toml"))

    def test_valid_file_returns_path(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("[qat]")
        result = resolve_qat_config_path(str(config_file))
        assert result == config_file


class TestGracefulKill:
    def create_fake_server(self):
        """Helper to create a fake server with a stop method."""

        class _FakeServer:
            def __init__(self):
                self.stopped = False

            def stop(self):
                self.stopped = True

        return _FakeServer()

    @pytest.mark.parametrize("signal", [SIGINT, SIGTERM])
    def test_handle_signal_stops_server(self, signal):
        server = self.create_fake_server()
        guard = GracefulKill(server)

        guard._handle_signal(signal, None)

        assert server.stopped is True

    def test_context_manager_installs_and_restores_handlers(self):
        server = self.create_fake_server()
        original_sigint_handler = getsignal(SIGINT)
        original_sigterm_handler = getsignal(SIGTERM)

        with GracefulKill(server) as guard:
            assert getsignal(SIGINT) == guard._handle_signal
            assert getsignal(SIGTERM) == guard._handle_signal

        assert getsignal(SIGINT) == original_sigint_handler
        assert getsignal(SIGTERM) == original_sigterm_handler
