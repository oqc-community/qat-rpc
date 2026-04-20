# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023-2026 Oxford Quantum Circuits Ltd
"""Unit tests for Pydantic message models."""

import pytest
from compiler_config.config import CompilerConfig
from pydantic import ValidationError

from qat_rpc.models import (
    CompileMessage,
    CompilePipelinesMessage,
    CouplingsMessage,
    ExecuteMessage,
    ExecutePipelinesMessage,
    ProgramMessage,
    QpuInfoMessage,
    QubitInfoMessage,
    VersionMessage,
)


class TestProgramMessage:
    def test_construction_with_defaults(self):
        msg = ProgramMessage(program="OPENQASM 2.0;", config=CompilerConfig())
        assert msg.program == "OPENQASM 2.0;"
        assert isinstance(msg.config, CompilerConfig)
        assert msg.compile_pipeline is None
        assert msg.execute_pipeline is None

    def test_construction_with_pipelines(self):
        msg = ProgramMessage(
            program="OPENQASM 2.0;",
            config=CompilerConfig(),
            compile_pipeline="custom_compile",
            execute_pipeline="custom_execute",
        )
        assert msg.compile_pipeline == "custom_compile"
        assert msg.execute_pipeline == "custom_execute"

    def test_frozen_immutability(self):
        msg = ProgramMessage(program="OPENQASM 2.0;", config=CompilerConfig())
        with pytest.raises(ValidationError):
            msg.program = "modified"

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            ProgramMessage.model_validate({})

        with pytest.raises(ValidationError):
            ProgramMessage.model_validate({"program": "OPENQASM 2.0;"})


class TestCompileMessage:
    def test_construction(self):
        msg = CompileMessage(program="OPENQASM 2.0;", config=CompilerConfig())
        assert msg.pipeline is None
        assert isinstance(msg.config, CompilerConfig)

    def test_with_pipeline(self):
        msg = CompileMessage(
            program="OPENQASM 2.0;", config=CompilerConfig(), pipeline="my_pipeline"
        )
        assert msg.pipeline == "my_pipeline"


class TestExecuteMessage:
    def test_construction_with_string_package(self):
        msg = ExecuteMessage(package="serialized_package", config=CompilerConfig())
        assert msg.package == "serialized_package"
        assert msg.pipeline is None
        assert isinstance(msg.config, CompilerConfig)

    def test_with_pipeline(self):
        msg = ExecuteMessage(
            package="serialized_package", config=CompilerConfig(), pipeline="exec_pipe"
        )
        assert msg.pipeline == "exec_pipe"


class TestVersionMessage:
    def test_construction(self):
        msg = VersionMessage()
        assert msg.model_dump() == {}


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


class TestPipelineQueryMessages:
    @pytest.mark.parametrize(
        "message_cls", [CompilePipelinesMessage, ExecutePipelinesMessage]
    )
    def test_construction(self, message_cls):
        msg = message_cls()
        assert msg.model_dump() == {}
