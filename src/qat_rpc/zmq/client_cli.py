# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023-2026 Oxford Quantum Circuits Ltd
"""Command-line interface for submitting programs to a QAT RPC server.

Exposed as the ``qat_comexe`` console script.
"""

import argparse
import sys
from pathlib import Path

from qat.purr.utils.logger import get_default_logger

from qat_rpc.zmq.client import ZMQClient

log = get_default_logger()

parser = argparse.ArgumentParser(
    prog="QAT submission service",
    description="Submit your QASM or QIR program to QAT RPC Server.",
)
parser.add_argument(
    "program", type=str, help="Program string or path to program file (.qasm, .ll, .bc)."
)
parser.add_argument(
    "--config", type=str, help="Serialized CompilerConfig JSON or path to JSON file."
)
parser.add_argument(
    "--host",
    type=str,
    default="127.0.0.1",
    help="Server IP address (default: 127.0.0.1)",
)
parser.add_argument("--port", type=int, default=5556, help="Server port (default: 5556)")


def _read_file_or_string(value: str, label: str) -> str | bytes:
    """Return file contents if *value* is a file path, otherwise return it as-is.

    Binary files (e.g. QIR bitcode `.bc`) are returned as `bytes`;
    all other files are returned as text.

    :param value: A file path or literal string (e.g. a program or config JSON).
    :param label: Descriptive name for *value* (e.g. `"program"` or `"config"`),
        used in error messages to identify which input failed to read.
    """
    path = Path(value)
    if path.is_file():
        try:
            if path.suffix == ".bc":
                return path.read_bytes()
            return path.read_text()
        except Exception:
            log.exception(f"Failed to read {label} file '{value}'")
            sys.exit(1)
    return value


def qat_run(args=None):
    """CLI entrypoint - parse arguments, connect, and execute."""
    args = parser.parse_args(args)

    program = _read_file_or_string(args.program, "program")
    config: str | None = (
        str(_read_file_or_string(args.config, "config"))
        if args.config is not None
        else None
    )

    # Connect to server and execute
    try:
        zmq_client = ZMQClient(client_ip=args.host, client_port=args.port)
        results = zmq_client.execute_task(program, config)
        print(results)
    except TimeoutError:
        log.exception("Server connection timeout")
        sys.exit(1)
    except Exception:
        log.exception("Execution failed")
        sys.exit(1)
