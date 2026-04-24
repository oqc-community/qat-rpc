# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023-2026 Oxford Quantum Circuits Ltd
"""Transport-agnostic QAT service logic."""

from pathlib import Path
from typing import Any

from compiler_config.config import CompilerConfig
from qat import QAT
from qat.executables import Executable
from qat.integrations.features import OpenPulseFeatures
from qat.model.hardware_model import PhysicalHardwareModel, QuantumHardwareModel
from qat.purr.compiler.builders import InstructionBuilder
from qat.purr.integrations.features import OpenPulseFeatures as PurrOpenPulseFeatures
from qat.purr.utils.logger import get_default_logger

from qat_rpc.metrics import MetricExporter
from qat_rpc.models import (
    CompiledProgram,
    CompilePipelinesRequest,
    CompileRequest,
    CouplingsRequest,
    ExecutePipelinesRequest,
    ExecuteRequest,
    ProgramRequest,
    QpuInfoRequest,
    QubitInfoRequest,
    Request,
    Response,
    Results,
    VersionRequest,
)

log = get_default_logger()


class QATServiceHandler:
    """Core RPC handler - owns the QAT instance and dispatches messages.

    Each public method corresponds to an RPC operation.  Transport layers
    (e.g. ``ZMQServer``) call ``handle(message)`` which routes to the
    correct method via pattern matching.
    """

    def __init__(
        self,
        metric_exporter: MetricExporter,
        qat_config_path: Path | None = None,
        compile_enabled: bool = True,
    ):
        self._metric = metric_exporter
        self._qat = QAT(qat_config_path)
        self._compile_enabled = compile_enabled

    @property
    def metric(self) -> MetricExporter:
        return self._metric

    # --- Pipeline helpers ---

    def _get_default_compile_pipeline_name(self) -> str:
        """Name of the QAT-configured default compile pipeline."""
        return self._qat.pipelines.default_compile_pipeline

    def _get_default_execute_pipeline_name(self) -> str:
        """Name of the QAT-configured default execute pipeline."""
        return self._qat.pipelines.default_execute_pipeline

    def _get_hardware(
        self, pipeline: str | None = None
    ) -> QuantumHardwareModel | PhysicalHardwareModel:
        """Resolve the hardware model from a named execute pipeline."""
        if pipeline is None:
            pipeline = self._get_default_execute_pipeline_name()
        return self._qat.pipelines.get_execute_pipeline(pipeline).model

    # --- Operations ---

    def compile(
        self, program: str | bytes, config: CompilerConfig, pipeline: str | None = None
    ) -> CompiledProgram:
        """Compile *program* and return the compiled package with metrics."""
        if pipeline is None:
            pipeline = self._get_default_compile_pipeline_name()
        package, metrics = self._qat.compile(program, config, pipeline)
        return CompiledProgram(package=package, compilation_metrics=metrics)

    def execute(
        self,
        package: InstructionBuilder | Executable | str,
        config: CompilerConfig,
        pipeline: str | None = None,
    ) -> Results:
        """Execute a compiled *package* and return results with metrics."""
        if pipeline is None:
            pipeline = self._get_default_execute_pipeline_name()
        results, metrics = self._qat.execute(package, config, pipeline)
        return Results(results=results, execution_metrics=metrics)

    def run_program(
        self,
        program: str | bytes,
        config: CompilerConfig,
        compile_pipeline: str | None = None,
        execute_pipeline: str | None = None,
    ) -> Results:
        """Compile and execute a program. Pipelines default if not specified."""
        compile_result = self.compile(program, config, compile_pipeline)
        execute_result = self.execute(compile_result.package, config, execute_pipeline)
        metrics = compile_result.compilation_metrics.merge(execute_result.execution_metrics)
        return Results(
            results=execute_result.results,
            execution_metrics=metrics,
        )

    def version(self) -> dict[str, str]:
        """Return the ``qat-rpc`` package version."""
        from qat_rpc import __version__

        return {"qat_rpc_version": __version__}

    def couplings(self, pipeline: str | None = None) -> dict[str, list]:
        """Return qubit couplings from the active hardware model.

        For PuRR ``QuantumHardwareModel`` we use ``qubit_direction_couplings``.
        For pydantic ``PhysicalHardwareModel`` we use ``logical_connectivity``
        which is its analogue - exposing only calibrated coupling directions.
        """
        hardware = self._get_hardware(pipeline)
        if isinstance(hardware, QuantumHardwareModel):
            coupling_list = [
                coupled.direction for coupled in hardware.qubit_direction_couplings
            ]
        else:
            logical_connectivity = hardware.logical_connectivity or {}
            coupling_list = [
                (q1, q2)
                for q1, connected_qubits in logical_connectivity.items()
                for q2 in connected_qubits
            ]
        return {"couplings": coupling_list}

    def qubit_info(self, pipeline: str | None = None) -> dict[str, Any]:
        """Return per-qubit information (not yet implemented)."""
        raise NotImplementedError(
            "Individual qubit information not implemented, pending hardware model changes."
        )

    def compile_pipelines(self) -> dict[str, Any]:
        """Return available compile pipelines and the current default."""
        return {
            "compile_pipelines": self._qat.pipelines.list_compile_pipelines,
            "default": self._get_default_compile_pipeline_name(),
        }

    def execute_pipelines(self) -> dict[str, Any]:
        """Return available execute pipelines and the current default."""
        return {
            "execute_pipelines": self._qat.pipelines.list_execute_pipelines,
            "default": self._get_default_execute_pipeline_name(),
        }

    def qpu_info(self, pipeline: str | None = None) -> dict[str, Any]:
        """Return aggregate QPU hardware information via OpenPulse."""
        hardware = self._get_hardware(pipeline)
        if isinstance(hardware, QuantumHardwareModel):
            features = PurrOpenPulseFeatures()
            features.for_hardware(hardware)
        else:
            features = OpenPulseFeatures.from_hardware(hardware)
        return {"qpu_info": features.to_json_dict()}

    # --- Message dispatch ---

    def handle(self, request: Request) -> Response:
        """Dispatch a ``Request`` to the corresponding operation and return its response."""
        log.info(f"Handling request: {type(request).__name__}, {request}")
        match request:
            case ProgramRequest(
                program=program,
                config=config,
                compile_pipeline=compile_pipeline,
                execute_pipeline=execute_pipeline,
            ):
                return self.run_program(program, config, compile_pipeline, execute_pipeline)

            case CompileRequest(program=program, config=config, pipeline=pipeline):
                if not self._compile_enabled:
                    raise NotImplementedError("Compile endpoint is disabled.")
                return self.compile(program, config, pipeline)

            case ExecuteRequest(package=package, config=config, pipeline=pipeline):
                return self.execute(package, config, pipeline)

            case VersionRequest():
                return self.version()

            case CouplingsRequest(pipeline=pipeline):
                return self.couplings(pipeline)

            case QubitInfoRequest(pipeline=pipeline):
                return self.qubit_info(pipeline)

            case QpuInfoRequest(pipeline=pipeline):
                return self.qpu_info(pipeline)

            case CompilePipelinesRequest():
                return self.compile_pipelines()

            case ExecutePipelinesRequest():
                return self.execute_pipelines()

            case _:
                raise ValueError(f"Unrecognized request: {request}")
