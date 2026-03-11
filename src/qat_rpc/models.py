"""Wire protocol vocabulary for QAT RPC.

Pydantic models that define the RPC message contract between client and
server, plus the ``Message`` and ``Response`` type aliases used across
the handler and transport layers.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict
from qat.core.metrics_base import MetricsManager
from qat.executables import Executable
from qat.purr.compiler.builders import InstructionBuilder

# --- Request messages (client -> server) ---


class _FrozenMessage(BaseModel):
    """Immutable base for request messages.

    Frozen so messages are hashable and cannot be mutated after creation.
    ``arbitrary_types_allowed`` permits QAT-internal types like
    ``InstructionBuilder`` as fields.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)


class ProgramMessage(_FrozenMessage):
    """Compile and execute a program in a single round-trip."""

    program: str
    config: str
    compile_pipeline: str | None = None
    execute_pipeline: str | None = None


class CompileMessage(_FrozenMessage):
    """Compile a program without executing it."""

    program: str
    config: str
    pipeline: str | None = None


class ExecuteMessage(_FrozenMessage):
    """Execute a previously compiled package."""

    package: InstructionBuilder | Executable | str
    config: str
    pipeline: str | None = None


class VersionMessage(_FrozenMessage):
    """Request the server's API version."""


class CouplingsMessage(_FrozenMessage):
    """Request qubit coupling directions from the hardware model."""

    pipeline: str | None = None


class QubitInfoMessage(_FrozenMessage):
    """Request per-qubit hardware information."""

    pipeline: str | None = None


class QpuInfoMessage(_FrozenMessage):
    """Request aggregate QPU hardware information."""

    pipeline: str | None = None


class CompilePipelinesMessage(_FrozenMessage):
    """Request the list of available compile pipelines."""


class ExecutePipelinesMessage(_FrozenMessage):
    """Request the list of available execute pipelines."""


Message = (
    ProgramMessage
    | CompileMessage
    | ExecuteMessage
    | VersionMessage
    | CouplingsMessage
    | QubitInfoMessage
    | QpuInfoMessage
    | CompilePipelinesMessage
    | ExecutePipelinesMessage
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
