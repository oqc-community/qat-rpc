# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023-2026 Oxford Quantum Circuits Ltd
"""Wire protocol vocabulary for QAT RPC.

Pydantic models that define the RPC request/response contract between client
and server, plus the ``Request`` and ``Response`` type aliases used across
the handler and transport layers.
"""

from typing import Any

from compiler_config.config import CompilerConfig
from pydantic import BaseModel, ConfigDict
from qat.core.metrics_base import MetricsManager
from qat.executables import Executable
from qat.purr.compiler.builders import InstructionBuilder

# --- Request messages (client -> server) ---


class _FrozenRequest(BaseModel):
    """Immutable base for request messages.

    Frozen so requests are hashable and cannot be mutated after creation.
    ``arbitrary_types_allowed`` permits QAT-internal types like
    ``InstructionBuilder`` and ``CompilerConfig`` as fields.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)


class ProgramRequest(_FrozenRequest):
    """Compile and execute a program in a single round-trip."""

    program: str | bytes
    config: CompilerConfig
    compile_pipeline: str | None = None
    execute_pipeline: str | None = None


class CompileRequest(_FrozenRequest):
    """Compile a program without executing it."""

    program: str | bytes
    config: CompilerConfig
    pipeline: str | None = None


class ExecuteRequest(_FrozenRequest):
    """Execute a previously compiled package."""

    package: InstructionBuilder | Executable | str
    config: CompilerConfig
    pipeline: str | None = None


class VersionRequest(_FrozenRequest):
    """Request the server's API version."""


class CouplingsRequest(_FrozenRequest):
    """Request qubit coupling directions from the hardware model."""

    pipeline: str | None = None


class QubitInfoRequest(_FrozenRequest):
    """Request per-qubit hardware information."""

    pipeline: str | None = None


class QpuInfoRequest(_FrozenRequest):
    """Request aggregate QPU hardware information."""

    pipeline: str | None = None


class CompilePipelinesRequest(_FrozenRequest):
    """Request the list of available compile pipelines."""


class ExecutePipelinesRequest(_FrozenRequest):
    """Request the list of available execute pipelines."""


Request = (
    ProgramRequest
    | CompileRequest
    | ExecuteRequest
    | VersionRequest
    | CouplingsRequest
    | QubitInfoRequest
    | QpuInfoRequest
    | CompilePipelinesRequest
    | ExecutePipelinesRequest
)


# --- Response types (server -> client) ---


class Results(BaseModel):
    """Results from program execution."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    results: dict[Any, Any]
    execution_metrics: MetricsManager


class CompiledProgram(BaseModel):
    """Results from program compilation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    package: InstructionBuilder | Executable | str
    compilation_metrics: MetricsManager


Response = Results | CompiledProgram | dict[str, Any]
