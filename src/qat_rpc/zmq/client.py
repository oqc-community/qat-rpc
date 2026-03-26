"""ZMQ REQ client for QAT RPC."""

from typing import Any

import zmq
from compiler_config.config import CompilerConfig
from qat.executables import Executable
from qat.purr.compiler.builders import InstructionBuilder

from qat_rpc.models import (
    CompileMessage,
    CompilePipelinesMessage,
    CouplingsMessage,
    ExecuteMessage,
    ExecutePipelinesMessage,
    Message,
    ProgramMessage,
    QpuInfoMessage,
    QubitInfoMessage,
    VersionMessage,
)
from qat_rpc.zmq._base import ZMQBase


class ZMQClient(ZMQBase):
    """ZMQ REQ client - one method per RPC operation.

    Each public method constructs the appropriate ``Message``, sends it,
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

    def _send_and_receive(self, message: Message) -> dict[str, Any]:
        """Send a message and return the server's reply."""
        self._send(message)
        return self._await_results()

    def _build_config(self, config: CompilerConfig | str | None) -> str:
        """Normalise *config* to a JSON string, applying defaults when ``None``."""
        if isinstance(config, str):
            return CompilerConfig.create_from_json(config).to_json()
        return (config or CompilerConfig()).to_json()

    def execute_task(
        self,
        program: str,
        config: CompilerConfig | str | None = None,
        compile_pipeline: str | None = None,
        execute_pipeline: str | None = None,
    ) -> dict[str, Any]:
        """Compile and execute a program.

        Pipeline arguments are optional; the server uses its defaults when omitted.
        """
        return self._send_and_receive(
            ProgramMessage(
                program=program,
                config=self._build_config(config),
                compile_pipeline=compile_pipeline,
                execute_pipeline=execute_pipeline,
            )
        )

    def compile_program(
        self,
        program: str,
        config: CompilerConfig | str | None = None,
        pipeline: str | None = None,
    ) -> dict[str, Any]:
        """Compile a program, optionally targeting a specific pipeline."""
        return self._send_and_receive(
            CompileMessage(
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
            ExecuteMessage(
                package=compiled_program,
                config=self._build_config(config),
                pipeline=pipeline,
            )
        )

    def api_version(self) -> dict[str, Any]:
        """Request the server's API version."""
        return self._send_and_receive(VersionMessage())

    def qpu_couplings(self, pipeline: str | None = None) -> dict[str, Any]:
        """Request qubit coupling directions."""
        return self._send_and_receive(CouplingsMessage(pipeline=pipeline))

    def qubit_info(self, pipeline: str | None = None) -> dict[str, Any]:
        """Request individual qubit information."""
        return self._send_and_receive(QubitInfoMessage(pipeline=pipeline))

    def qpu_info(self, pipeline: str | None = None) -> dict[str, Any]:
        """Request QPU hardware information."""
        return self._send_and_receive(QpuInfoMessage(pipeline=pipeline))

    def compile_pipelines(self) -> dict[str, Any]:
        """Request the list of available compile pipelines."""
        return self._send_and_receive(CompilePipelinesMessage())

    def execute_pipelines(self) -> dict[str, Any]:
        """Request the list of available execute pipelines."""
        return self._send_and_receive(ExecutePipelinesMessage())
