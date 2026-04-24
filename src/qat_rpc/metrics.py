# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023-2026 Oxford Quantum Circuits Ltd
"""Pluggable metrics framework for QAT RPC.

Backends (e.g. ``PrometheusReceiver``) define the metrics surface.
``MetricExporter`` dynamically mirrors a backend's public methods as
context managers that yield mutable outcome objects.
"""

import abc
import inspect
import re
from collections.abc import Callable
from inspect import getmembers, ismethod
from typing import Generic, TypeVar

from prometheus_client import Counter, Gauge, start_http_server
from qat.purr.utils.logger import get_default_logger

log = get_default_logger()

DEFAULT_PROMETHEUS_PORT = 9250


class IncrementMutableOutcome:
    """Accumulator yielded by increment-style metric context managers."""

    def __init__(self):
        self._count: float = 0.0

    def increment(self, amount: float = 1.0):
        self._count += amount

    def __float__(self):
        return self._count

    def __int__(self):
        return int(self._count)


class BinaryMutableOutcome:
    """Success/failure flag yielded by binary metric context managers."""

    def __init__(self):
        self._success: bool | None = None

    def succeed(self):
        # Failure is sticky
        if self._success is None or self._success:
            self._success = True

    def fail(self):
        self._success = False

    def __int__(self):
        return int(self._success)

    def __float__(self):
        return 1.0 if self._success else 0.0

    def __eq__(self, other):
        if isinstance(other, BinaryMutableOutcome):
            return other is not None and other._success == self._success
        if isinstance(other, bool):
            return (self is not None and not other) or (other == self._success)


class ReceiverBackend(abc.ABC):
    """Abstract metrics backend — defines the metrics surface via its public methods."""

    @abc.abstractmethod
    def receiver_status(self, outcome: BinaryMutableOutcome) -> None: ...

    @abc.abstractmethod
    def failed_messages(self, outcome: IncrementMutableOutcome) -> None: ...

    @abc.abstractmethod
    def executed_messages(self, outcome: IncrementMutableOutcome) -> None: ...

    @abc.abstractmethod
    def hardware_connected(self, outcome: BinaryMutableOutcome) -> None: ...

    @abc.abstractmethod
    def hardware_reloaded(self, outcome: BinaryMutableOutcome) -> None: ...


class NullReceiverBackend(ReceiverBackend):
    """No-op backend for testing or when metrics are disabled."""

    def __init__(self):
        super().__init__()

    def receiver_status(self, outcome: BinaryMutableOutcome) -> None: ...

    def failed_messages(self, outcome: IncrementMutableOutcome) -> None: ...

    def executed_messages(self, outcome: IncrementMutableOutcome) -> None: ...

    def hardware_connected(self, outcome: BinaryMutableOutcome) -> None: ...

    def hardware_reloaded(self, outcome: BinaryMutableOutcome) -> None: ...


class PrometheusReceiver(ReceiverBackend):
    """Prometheus-backed metrics receiver."""

    def __init__(self, port: int = DEFAULT_PROMETHEUS_PORT):
        super().__init__()
        start_http_server(port)
        log.info(f"Starting Prometheus metrics exporter on port {port}.")

        self._receiver_status = Gauge(
            "receiver_status", "Measure the Receiver backend up state"
        )
        self._failed_messages = Counter("failed_messages", "messages failure counter")
        self._executed_messages = Counter("executed_messages", "messages executed counter")
        self._hardware_connected_status = Gauge(
            "hardware_connected_status",
            "Indicate connected status of live hardware",
        )
        self._hardware_reloaded_status = Gauge(
            "hardware_reloaded_status",
            "Indicate if hardware reload from calibration succeeded or failed",
        )

    def receiver_status(self, outcome: BinaryMutableOutcome) -> None:
        self._receiver_status.set(outcome)

    def failed_messages(self, outcome: IncrementMutableOutcome) -> None:
        self._failed_messages.inc(float(outcome))

    def executed_messages(self, outcome: IncrementMutableOutcome) -> None:
        self._executed_messages.inc(float(outcome))

    def hardware_connected(self, outcome: BinaryMutableOutcome) -> None:
        self._hardware_connected_status.set(outcome)

    def hardware_reloaded(self, outcome: BinaryMutableOutcome) -> None:
        self._hardware_reloaded_status.set(outcome)


class ReceiverAdapter(ReceiverBackend):
    """Adapter that delegates to a wrapped ``ReceiverBackend``.

    Preserves the interface that ``MetricExporter`` relies
    on for introspection when the underlying backend is proxied or
    decorated.
    """

    def __init__(self, decorated: ReceiverBackend):
        self.decorated = decorated

    def receiver_status(self, outcome: BinaryMutableOutcome) -> None:
        self.decorated.receiver_status(outcome)

    def failed_messages(self, outcome: IncrementMutableOutcome) -> None:
        self.decorated.failed_messages(outcome)

    def executed_messages(self, outcome: IncrementMutableOutcome) -> None:
        self.decorated.executed_messages(outcome)

    def hardware_connected(self, outcome: BinaryMutableOutcome) -> None:
        self.decorated.hardware_connected(outcome)

    def hardware_reloaded(self, outcome: BinaryMutableOutcome) -> None:
        self.decorated.hardware_reloaded(outcome)


# Generic type variable for outcome types
T = TypeVar("T", IncrementMutableOutcome, BinaryMutableOutcome)


class MetricFieldWrapper(Generic[T]):
    """Context manager that yields a mutable outcome, then pushes it to the backend."""

    def __init__(
        self,
        func: Callable,
        outcome: T,
    ):
        self.callable = func
        self.outcome = outcome

    def __enter__(self) -> T:
        # Loan out the mutable outcome for change
        return self.outcome

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Apply the outcome to target callable
        try:
            self.callable(self.outcome)
        except Exception as ex:
            log.warning(f"Metric setting errored {ex!s}")


class MetricExporter:
    """Dynamic factory for metric context managers.

    Introspects a ``ReceiverBackend`` and creates a no-arg method for each
    of its public methods.  Each generated method returns a
    ``MetricFieldWrapper`` context manager.
    """

    def __init__(self, backend: ReceiverBackend):
        if isinstance(backend, type):
            raise TypeError("Argument must be an instance not a type")
        methods = [
            member
            for member in getmembers(backend, predicate=ismethod)
            if not re.match("^_", member[0])
        ]

        def decorate(f):
            # factory function avoids closure issues
            try:
                sign = inspect.signature(f)
                parameters = sign.parameters
                outcome_param = parameters.get("outcome")
                outcome_type = outcome_param.annotation
                return lambda: MetricFieldWrapper(f, outcome_type())
            except KeyError:
                log.exception(
                    "An error occurred while processing the function's outcome parameter"
                )
                raise

        for func_name, func in methods:
            nargs = func.__code__.co_argcount
            if not nargs == 2:
                raise ValueError(
                    f"Receiver must have one non-self argument on each "
                    f"function. Found {nargs} while evaluating {func_name}"
                    f" on {type(backend)!s}"
                )
            # build no-arg setting functions on this matching backend public name
            setattr(self, func_name, decorate(func))

    # Type hints for dynamically created methods (created via setattr in __init__)
    # Each method returns a context manager that yields the specific outcome type
    def receiver_status(self) -> MetricFieldWrapper[BinaryMutableOutcome]: ...
    def failed_messages(self) -> MetricFieldWrapper[IncrementMutableOutcome]: ...
    def executed_messages(self) -> MetricFieldWrapper[IncrementMutableOutcome]: ...
    def hardware_connected(self) -> MetricFieldWrapper[BinaryMutableOutcome]: ...
    def hardware_reloaded(self) -> MetricFieldWrapper[BinaryMutableOutcome]: ...
