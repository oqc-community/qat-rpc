"""Unit tests for Pydantic message models."""

import pytest
from pydantic import ValidationError

from qat_rpc.models import (
    CompileMessage,
    CouplingsMessage,
    ExecuteMessage,
    ProgramMessage,
    QpuInfoMessage,
    QubitInfoMessage,
    VersionMessage,
)


class TestProgramMessage:
    def test_construction_with_defaults(self):
        msg = ProgramMessage(program="OPENQASM 2.0;", config="{}")
        assert msg.program == "OPENQASM 2.0;"
        assert msg.config == "{}"
        assert msg.compile_pipeline is None
        assert msg.execute_pipeline is None

    def test_construction_with_pipelines(self):
        msg = ProgramMessage(
            program="OPENQASM 2.0;",
            config="{}",
            compile_pipeline="custom_compile",
            execute_pipeline="custom_execute",
        )
        assert msg.compile_pipeline == "custom_compile"
        assert msg.execute_pipeline == "custom_execute"

    def test_frozen_immutability(self):
        msg = ProgramMessage(program="OPENQASM 2.0;", config="{}")
        with pytest.raises(ValidationError):
            msg.program = "modified"

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            ProgramMessage.model_validate({})

        with pytest.raises(ValidationError):
            ProgramMessage.model_validate({"program": "OPENQASM 2.0;"})

        with pytest.raises(ValidationError):
            ProgramMessage.model_validate({"config": "{}"})


class TestCompileMessage:
    def test_construction(self):
        msg = CompileMessage(program="OPENQASM 2.0;", config="{}")
        assert msg.pipeline is None

    def test_with_pipeline(self):
        msg = CompileMessage(program="OPENQASM 2.0;", config="{}", pipeline="my_pipeline")
        assert msg.pipeline == "my_pipeline"


class TestExecuteMessage:
    def test_construction_with_string_package(self):
        msg = ExecuteMessage(package="serialized_package", config="{}")
        assert msg.package == "serialized_package"
        assert msg.pipeline is None

    def test_with_pipeline(self):
        msg = ExecuteMessage(
            package="serialized_package", config="{}", pipeline="exec_pipe"
        )
        assert msg.pipeline == "exec_pipe"


class TestVersionMessage:
    def test_construction(self):
        msg = VersionMessage()
        assert msg is not None


class TestHardwareInfoMessages:
    @pytest.mark.parametrize(
        "message", [CouplingsMessage, QubitInfoMessage, QpuInfoMessage]
    )
    def test_construction_with_defaults(self, message):
        msg = message()
        assert msg.pipeline is None

    @pytest.mark.parametrize(
        "message", [CouplingsMessage, QubitInfoMessage, QpuInfoMessage]
    )
    def test_construction_with_pipeline(self, message):
        msg = message(pipeline="pipeline")
        assert msg.pipeline == "pipeline"
