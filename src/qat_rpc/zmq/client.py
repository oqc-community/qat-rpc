# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023-2026 Oxford Quantum Circuits Ltd
"""ZMQ REQ client for QAT RPC."""

from typing import Any

import zmq
from compiler_config.config import CompilerConfig
from qat.executables import Executable
from qat.purr.compiler.builders import InstructionBuilder

from qat_rpc.models import (
    CompilePipelinesRequest,
    CompileRequest,
    CouplingsRequest,
    ExecutePipelinesRequest,
    ExecuteRequest,
    ProgramRequest,
    QpuInfoRequest,
    QubitInfoRequest,
    Request,
    VersionRequest,
)
from qat_rpc.zmq._base import ZMQBase


class ZMQClient(ZMQBase):
    """ZMQ REQ client - one method per RPC operation.

    Each public method constructs the appropriate ``Request``, sends it,
    and blocks until the server replies.  Responses are always plain dicts
    (see ``ZMQServer._serialize_response``).
    """

    def __init__(
        self,
        client_ip: str = "127.0.0.1",
        client_port: int = 5556,
        timeout: float = 30.0,
    ):
        super().__init__(
            socket_type=zmq.REQ, ip_address=client_ip, port=client_port, timeout=timeout
        )
        self._socket.connect(self.address)

    def _await_results(self) -> dict[str, Any]:
        """Block until the server replies, raising on timeout."""
        return self._receive(timeout=self._timeout, raise_on_timeout=True)

    def _send_and_receive(self, request: Request) -> dict[str, Any]:
        """Send a request and return the server's reply."""
        self._send(request)
        return self._await_results()

    @staticmethod
    def _build_config(config: CompilerConfig | str | None) -> CompilerConfig:
        """Normalise *config* to a ``CompilerConfig``, applying defaults when ``None``."""
        if isinstance(config, str):
            return CompilerConfig.create_from_json(config)
        return config or CompilerConfig()

    def execute_task(
        self,
        program: str | bytes,
        config: CompilerConfig | str | None = None,
        compile_pipeline: str | None = None,
        execute_pipeline: str | None = None,
    ) -> dict[str, Any]:
        """Compile and execute a program.

        :param program: An OpenQASM 2.0, OpenQASM 3.0, or QIR program.
            Accepts a source string (QASM / QIR text) or raw QIR bitcode bytes.

        Pipeline arguments are optional; the server uses its defaults when omitted.
        """
        return self._send_and_receive(
            ProgramRequest(
                program=program,
                config=self._build_config(config),
                compile_pipeline=compile_pipeline,
                execute_pipeline=execute_pipeline,
            )
        )

    def compile_program(
        self,
        program: str | bytes,
        config: CompilerConfig | str | None = None,
        pipeline: str | None = None,
    ) -> dict[str, Any]:
        """Compile a program, optionally targeting a specific pipeline.

        :param program: An OpenQASM 2.0, OpenQASM 3.0, or QIR program.
            Accepts a source string (QASM / QIR text) or raw QIR bitcode bytes.
        """
        return self._send_and_receive(
            CompileRequest(
                program=program,
                config=self._build_config(config),
                pipeline=pipeline,
            )
        )

    def execute_compiled(
        self,
        compiled_program: InstructionBuilder | Executable | str,
        config: CompilerConfig | str | None = None,
        pipeline: str | None = None,
    ) -> dict[str, Any]:
        """Execute a pre-compiled program, optionally targeting a specific pipeline."""
        return self._send_and_receive(
            ExecuteRequest(
                package=compiled_program,
                config=self._build_config(config),
                pipeline=pipeline,
            )
        )

    def api_version(self) -> dict[str, Any]:
        """Request the server's API version."""
        return self._send_and_receive(VersionRequest())

    def qpu_couplings(self, pipeline: str | None = None) -> dict[str, Any]:
        """Request qubit coupling directions."""
        return self._send_and_receive(CouplingsRequest(pipeline=pipeline))

    def qubit_info(self, pipeline: str | None = None) -> dict[str, Any]:
        """Request individual qubit information."""
        return self._send_and_receive(QubitInfoRequest(pipeline=pipeline))

    def qpu_info(self, pipeline: str | None = None) -> dict[str, Any]:
        """Request QPU hardware information."""
        return self._send_and_receive(QpuInfoRequest(pipeline=pipeline))

    def compile_pipelines(self) -> dict[str, Any]:
        """Request the list of available compile pipelines."""
        return self._send_and_receive(CompilePipelinesRequest())

    def execute_pipelines(self) -> dict[str, Any]:
        """Request the list of available execute pipelines."""
        return self._send_and_receive(ExecutePipelinesRequest())
