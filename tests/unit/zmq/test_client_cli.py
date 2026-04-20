"""Unit tests for command-line client behavior."""

from unittest.mock import MagicMock

import pytest

import qat_rpc.zmq.client_cli as client_cli


@pytest.fixture()
def fake_client(monkeypatch):
    """Patch ZMQClient with a MagicMock, reset between tests."""
    mock_cls = MagicMock()
    monkeypatch.setattr(client_cli, "ZMQClient", mock_cls)
    return mock_cls


class TestReadFileOrString:
    def test_returns_string_when_path_does_not_exist(self):
        assert (
            client_cli._read_file_or_string("OPENQASM 2.0;", "program") == "OPENQASM 2.0;"
        )

    def test_reads_file_contents_when_path_exists(self, tmp_path):
        program_file = tmp_path / "program.qasm"
        program_file.write_text("OPENQASM 2.0;")

        assert (
            client_cli._read_file_or_string(str(program_file), "program") == "OPENQASM 2.0;"
        )

    def test_read_failure_exits_with_code_1(self, tmp_path):
        unreadable = tmp_path / "program.qasm"
        unreadable.write_text("content")
        unreadable.chmod(0o000)

        with pytest.raises(SystemExit, match="1"):
            client_cli._read_file_or_string(str(unreadable), "program")

        unreadable.chmod(0o644)  # restore so tmp_path cleanup succeeds


class TestQatRun:
    def test_success_with_inline_program(self, fake_client, capsys):
        fake_client.return_value.execute_task.return_value = {"ok": True}

        client_cli.qat_run(["OPENQASM 2.0;"])

        fake_client.assert_called_once_with(client_ip="127.0.0.1", client_port=5556)
        fake_client.return_value.execute_task.assert_called_once_with("OPENQASM 2.0;", None)
        assert "{'ok': True}" in capsys.readouterr().out

    def test_success_with_program_and_config_files(self, tmp_path, fake_client):
        program_file = tmp_path / "program.qasm"
        config_file = tmp_path / "config.json"
        program_file.write_text("OPENQASM 2.0;")
        config_file.write_text('{"repeats": 10}')

        fake_client.return_value.execute_task.return_value = {"results": {}}

        client_cli.qat_run(
            [
                str(program_file),
                "--config",
                str(config_file),
                "--host",
                "localhost",
                "--port",
                "6000",
            ]
        )

        fake_client.assert_called_once_with(client_ip="localhost", client_port=6000)
        fake_client.return_value.execute_task.assert_called_once_with(
            "OPENQASM 2.0;", '{"repeats": 10}'
        )

    @pytest.mark.parametrize("error", [TimeoutError("timeout"), RuntimeError("boom")])
    def test_errors_exit_with_code_1(self, fake_client, error):
        fake_client.return_value.execute_task.side_effect = error

        with pytest.raises(SystemExit, match="1"):
            client_cli.qat_run(["OPENQASM 2.0;"])
