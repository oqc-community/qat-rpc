# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023-2026 Oxford Quantum Circuits Ltd
"""Unit tests for Pydantic request models."""

import pytest
from compiler_config.config import CompilerConfig
from pydantic import ValidationError

from qat_rpc.models import (
    CompilePipelinesRequest,
    CompileRequest,
    CouplingsRequest,
    ExecutePipelinesRequest,
    ExecuteRequest,
    ProgramRequest,
    QpuInfoRequest,
    QubitInfoRequest,
    VersionRequest,
)


class TestProgramRequest:
    def test_construction_with_defaults(self):
        msg = ProgramRequest(program="OPENQASM 2.0;", config=CompilerConfig())
        assert msg.program == "OPENQASM 2.0;"
        assert isinstance(msg.config, CompilerConfig)
        assert msg.compile_pipeline is None
        assert msg.execute_pipeline is None

    def test_construction_with_pipelines(self):
        msg = ProgramRequest(
            program="OPENQASM 2.0;",
            config=CompilerConfig(),
            compile_pipeline="custom_compile",
            execute_pipeline="custom_execute",
        )
        assert msg.compile_pipeline == "custom_compile"
        assert msg.execute_pipeline == "custom_execute"

    def test_frozen_immutability(self):
        msg = ProgramRequest(program="OPENQASM 2.0;", config=CompilerConfig())
        with pytest.raises(ValidationError):
            msg.program = "modified"

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            ProgramRequest.model_validate({})

        with pytest.raises(ValidationError):
            ProgramRequest.model_validate({"program": "OPENQASM 2.0;"})


class TestCompileRequest:
    def test_construction(self):
        msg = CompileRequest(program="OPENQASM 2.0;", config=CompilerConfig())
        assert msg.pipeline is None
        assert isinstance(msg.config, CompilerConfig)

    def test_with_pipeline(self):
        msg = CompileRequest(
            program="OPENQASM 2.0;", config=CompilerConfig(), pipeline="my_pipeline"
        )
        assert msg.pipeline == "my_pipeline"


class TestExecuteRequest:
    def test_construction_with_string_package(self):
        msg = ExecuteRequest(package="serialized_package", config=CompilerConfig())
        assert msg.package == "serialized_package"
        assert msg.pipeline is None
        assert isinstance(msg.config, CompilerConfig)

    def test_with_pipeline(self):
        msg = ExecuteRequest(
            package="serialized_package", config=CompilerConfig(), pipeline="exec_pipe"
        )
        assert msg.pipeline == "exec_pipe"


class TestVersionRequest:
    def test_construction(self):
        msg = VersionRequest()
        assert msg.model_dump() == {}


class TestHardwareInfoRequests:
    @pytest.mark.parametrize(
        "request_cls", [CouplingsRequest, QubitInfoRequest, QpuInfoRequest]
    )
    def test_construction_with_defaults(self, request_cls):
        msg = request_cls()
        assert msg.pipeline is None

    @pytest.mark.parametrize(
        "request_cls", [CouplingsRequest, QubitInfoRequest, QpuInfoRequest]
    )
    def test_construction_with_pipeline(self, request_cls):
        msg = request_cls(pipeline="pipeline")
        assert msg.pipeline == "pipeline"


class TestPipelineQueryRequests:
    @pytest.mark.parametrize(
        "request_cls", [CompilePipelinesRequest, ExecutePipelinesRequest]
    )
    def test_construction(self, request_cls):
        msg = request_cls()
        assert msg.model_dump() == {}
