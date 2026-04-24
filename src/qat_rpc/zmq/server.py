# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023-2026 Oxford Quantum Circuits Ltd
"""ZMQ REP server and entrypoint for QAT RPC.

``ZMQServer`` binds a REP socket that accepts both typed ``Request``
objects and legacy tuple formats (pre-1.0 clients), delegating all
business logic to ``QATServiceHandler``.

Can be started via the ``qat_server`` console script.
"""

import os
from pathlib import Path
from signal import SIGINT, SIGTERM, signal
from types import FrameType, TracebackType
from typing import Any

import zmq
from compiler_config.config import CompilerConfig
from qat.purr.utils.logger import get_default_logger

from qat_rpc.handler import QATServiceHandler
from qat_rpc.metrics import (
    DEFAULT_PROMETHEUS_PORT,
    MetricExporter,
    PrometheusReceiver,
)
from qat_rpc.models import (
    CouplingsRequest,
    ProgramRequest,
    QpuInfoRequest,
    QubitInfoRequest,
    Request,
    Response,
    VersionRequest,
)
from qat_rpc.zmq._base import ZMQBase

RECEIVER_PORT = 5556

log = get_default_logger()


class ZMQServer(ZMQBase):
    """ZMQ REP server — receive, dispatch, reply.

    Wraps a REP socket that blocks for incoming requests, converts legacy
    tuple formats if necessary, and forwards typed ``Request`` objects to
    ``QATServiceHandler.handle``.  Responses are serialised back to plain
    dicts for backwards compatibility.
    """

    def __init__(
        self,
        metric_exporter: MetricExporter,
        server_port: int = RECEIVER_PORT,
        qat_config_path: Path | None = None,
        timeout: float = 30.0,
        compile_enabled: bool = True,
    ):
        super().__init__(socket_type=zmq.REP, port=server_port, timeout=timeout)
        self._socket.bind(self.address)
        self._handler = QATServiceHandler(metric_exporter, qat_config_path, compile_enabled)
        self._running = False

    @property
    def address(self) -> str:
        return f"{self._protocol}://*:{self._port}"

    @staticmethod
    def _convert_legacy_message(raw: tuple[Any, ...]) -> Request:
        """Convert a legacy tuple into a typed ``Request``.

        Two legacy wire formats are supported:

        * **Pre-0.3.0**: ``(program, config)`` - 2-tuple, no type discriminator.
        * **0.3.0+**: ``(type_str, *args)`` - string discriminator first,
          e.g. ``("program", code, config)`` or ``("version",)``.

        Only operations that existed in legacy versions are handled here;
        ``compile`` and ``execute`` were introduced with typed requests
        and have no legacy tuple form.
        """
        if not raw:
            raise ValueError(f"Invalid legacy message: {raw}")

        # Pre-0.3.0 compat: 2-tuple without a type discriminator treated as program
        if len(raw) == 2 and raw[0] not in {
            "program",
            "version",
            "couplings",
            "qubit_info",
            "qpu_info",
        }:
            return ProgramRequest(
                program=raw[0], config=CompilerConfig.create_from_json(raw[1])
            )

        if not isinstance(raw[0], str):
            raise TypeError(f"Invalid legacy message: {raw}")

        msg_type = raw[0]
        args = raw[1:]

        match msg_type:
            case "program":
                if len(args) == 2:
                    return ProgramRequest(
                        program=args[0],
                        config=CompilerConfig.create_from_json(args[1]),
                    )
                if len(args) == 4:
                    return ProgramRequest(
                        program=args[0],
                        config=CompilerConfig.create_from_json(args[1]),
                        compile_pipeline=args[2] or None,
                        execute_pipeline=args[3] or None,
                    )
                raise ValueError(f"PROGRAM message expects 2 or 4 args, got {len(args)}.")
            case "version":
                return VersionRequest()
            case "couplings":
                return CouplingsRequest()
            case "qubit_info":
                return QubitInfoRequest()
            case "qpu_info":
                return QpuInfoRequest()
            case _:
                raise ValueError(f"Unrecognized legacy message type: {msg_type}")

    @staticmethod
    def _serialize_response(response: Response) -> dict[str, Any]:
        """Flatten a ``Response`` to a plain dict for the wire.

        Pydantic models are dumped via ``model_dump()``; plain dicts pass
        through.  This keeps the wire format stable for older (<1.0) clients.
        """
        if isinstance(response, dict):
            return response
        return response.model_dump()

    def run(self) -> None:
        """Enter the receive -> handle -> reply loop until ``stop()`` is called."""
        self._running = True
        with self._handler.metric.receiver_status() as metric:
            metric.succeed()

        while self._running:
            try:
                raw = self._receive(timeout=None)
                if raw is None:
                    continue

                # Everything after receiving MUST send a reply (REP socket).
                try:
                    if isinstance(raw, tuple):
                        msg = self._convert_legacy_message(raw)
                    else:
                        msg = raw
                    response = self._serialize_response(self._handler.handle(msg))
                    with self._handler.metric.executed_messages() as executed:
                        executed.increment()
                except Exception as e:
                    log.exception(f"Error processing message {raw}")
                    response = {"Exception": repr(e)}
                    with self._handler.metric.failed_messages() as failed:
                        failed.increment()
                self._send(response)

            except zmq.ZMQError as e:
                if e.errno == zmq.ETERM:
                    log.info("Context terminated, shutting down server.")
                    break
            except Exception:
                log.exception("Unexpected error in server loop")

    def stop(self) -> None:
        """Signal the server loop to exit."""
        self._running = False
        with self._handler.metric.receiver_status() as metric:
            metric.fail()


# ---------------------------------------------------------------------------
# Server entrypoint helpers
# ---------------------------------------------------------------------------


def validate_port(
    port_value: str | None,
    port_name: str,
    default_port: int,
    excluded_ports: set[int] | None = None,
) -> int:
    """Parse and validate a port from an environment variable string.

    Returns *default_port* when *port_value* is ``None``, non-numeric,
    outside the registerable range (1024-49151), or in *excluded_ports*.
    """
    if port_value is None:
        return default_port

    try:
        port = int(port_value)
    except ValueError:
        log.warning(f"Configured {port_name} port is not a valid integer.")
        log.info(f"Defaulting {port_name} to run on port {default_port}")
        return default_port

    if not (1024 < port < 49152):
        log.warning(
            f"{port_name.capitalize()} must be configured to run on a valid "
            f"port number between 1024 and 49152."
        )
        log.info(f"Defaulting {port_name} to run on port {default_port}.")
        return default_port

    if excluded_ports is not None and port in excluded_ports:
        log.warning(
            f"{port_name.capitalize()} cannot run on port {port}, "
            f"it conflicts with another service."
        )
        log.info(f"Defaulting {port_name} to run on port {default_port}.")
        return default_port

    log.info(f"{port_name.capitalize()} is configured to start on port {port}.")
    return port


def resolve_qat_config_path(env_var_value: str | None) -> Path | None:
    """Resolve a QAT config file path from an environment variable.

    Relative paths are resolved against this module's directory.
    Returns ``None`` when *env_var_value* is not set (echo-mode default).

    Raises:
        ValueError: If the resolved path does not point to an existing file.
    """
    if env_var_value is not None:
        qat_config_path = Path(env_var_value)
        if not qat_config_path.is_absolute():
            qat_config_path = Path(__file__).parent / qat_config_path

        if not qat_config_path.is_file():
            raise ValueError(f"QAT config file not found: {qat_config_path}")

        log.info(f"Using QAT config: {qat_config_path}")
        return qat_config_path
    else:
        log.info("No QAT_CONFIG_PATH set, using default echo mode")
        return None


class GracefulKill:
    """Context manager that calls ``server.stop()`` on SIGINT/SIGTERM."""

    def __init__(self, server: ZMQServer):
        self.server = server
        self._original_sigint = None
        self._original_sigterm = None

    def __enter__(self) -> "GracefulKill":
        """Install signal handlers."""
        # Note: signal() returns the previous handler, which we store to restore later.
        self._original_sigint = signal(SIGINT, self._handle_signal)
        self._original_sigterm = signal(SIGTERM, self._handle_signal)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """Restore original signal handlers."""
        if self._original_sigint is not None:
            signal(SIGINT, self._original_sigint)
        if self._original_sigterm is not None:
            signal(SIGTERM, self._original_sigterm)
        return False  # Don't suppress exceptions

    def _handle_signal(self, signum: int, frame: FrameType | None) -> None:
        """Signal handler that stops the server."""
        signal_name = "SIGINT" if signum == SIGINT else "SIGTERM"
        log.info(f"Received {signal_name}, shutting down gracefully...")
        self.server.stop()


def main() -> None:
    """Server entrypoint — configure from environment variables and run."""
    # Validate receiver port first
    receiver_port = validate_port(os.getenv("RECEIVER_PORT"), "receiver", RECEIVER_PORT)

    # Validate metrics port, ensuring it doesn't conflict with receiver
    metrics_port = validate_port(
        os.getenv("METRICS_PORT"),
        "metrics exporter",
        DEFAULT_PROMETHEUS_PORT,
        excluded_ports={receiver_port},
    )

    metric_exporter = MetricExporter(backend=PrometheusReceiver(port=metrics_port))

    # Resolve QAT config path from environment or use default
    qat_config_path = resolve_qat_config_path(os.getenv("QAT_CONFIG_PATH"))

    # Feature flag: enable/disable compile and execute endpoints
    compile_enabled = os.getenv("ENABLE_COMPILE_ENDPOINT", "true").lower() == "true"
    if not compile_enabled:
        log.info("Compile and execute endpoints are disabled.")

    server = ZMQServer(
        metric_exporter=metric_exporter,
        server_port=receiver_port,
        qat_config_path=qat_config_path,
        compile_enabled=compile_enabled,
    )

    log.info(f"QAT RPC Server Starting, address: {server.address}")

    with GracefulKill(server):
        server.run()


if __name__ == "__main__":
    main()
