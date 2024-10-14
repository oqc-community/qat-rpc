import abc
import inspect
import re
from inspect import getmembers, ismethod
from typing import Callable, Union

from prometheus_client import Counter, Gauge, start_http_server
from qat.purr.utils.logger import get_default_logger

from qat_rpc.utils.constants import PROMETHEUS_PORT

log = get_default_logger()


class IncrementMutableOutcome:
    def __init__(self):
        self._count: float = 0.0

    def increment(self, amount: float = 1.0):
        self._count += amount

    def __float__(self):
        return self._count

    def __int__(self):
        return int(self._count)


class BinaryMutableOutcome:
    def __init__(self):
        self._success: bool = None

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
    @abc.abstractmethod
    def receiver_status(self, outcome: BinaryMutableOutcome): ...

    @abc.abstractmethod
    def failed_messages(self, outcome: IncrementMutableOutcome): ...

    @abc.abstractmethod
    def executed_messages(self, outcome: IncrementMutableOutcome): ...

    @abc.abstractmethod
    def hardware_connected(self, outcome: BinaryMutableOutcome): ...

    @abc.abstractmethod
    def hardware_reloaded(self, outcome: BinaryMutableOutcome): ...


class NullReceiverBackend(ReceiverBackend):
    def __init__(self):
        super(NullReceiverBackend, self).__init__()

    def receiver_status(self, outcome: BinaryMutableOutcome): ...

    def failed_messages(self, outcome: IncrementMutableOutcome): ...

    def executed_messages(self, outcome: IncrementMutableOutcome): ...

    def hardware_connected(self, outcome: BinaryMutableOutcome): ...

    def hardware_reloaded(self, outcome: BinaryMutableOutcome): ...


class PrometheusReceiver(ReceiverBackend):
    def __init__(self, port: int):
        super(PrometheusReceiver, self).__init__()
        start_http_server(port=PROMETHEUS_PORT)
        log.info(f"Using Prometheus on port {port}")

        self._receiver_status = Gauge(
            "receiver_status", "Measure the Receiver backend up state"
        )
        self._failed_messages = Counter("failed_messages", "messages failure counter")
        self._executed_messages = Counter("executed_messages", "messages executed counter")
        self._hardware_connected_status = Gauge(
            "hardware_connected_status", "Indicate connected status of live hardware"
        )
        self._hardware_reloaded_status = Gauge(
            "hardware_reloaded_status",
            "Indicate if hardware reload from calibration succeeded or failed",
        )

    def receiver_status(self, outcome: BinaryMutableOutcome):
        self._receiver_status.set(outcome)

    def failed_messages(self, outcome: IncrementMutableOutcome):
        self._failed_messages.inc(float(outcome))

    def executed_messages(self, outcome: IncrementMutableOutcome):
        self._executed_messages.inc(float(outcome))

    def hardware_connected(self, outcome: BinaryMutableOutcome):
        self._hardware_connected_status.set(outcome)

    def hardware_reloaded(self, outcome: BinaryMutableOutcome):
        self._hardware_reloaded_status.set(outcome)


class ReceiverAdapter(ReceiverBackend):
    """
    Presents a normal derived type to the MetricsExporter which is required for
    introspection as part of it's dynamic build. When using Mocks, which replace
    functions with variables, it is required to first wrap those in Adapters.
    """

    def __init__(self, decorated):
        self.decorated = decorated

    def receiver_status(self, outcome: BinaryMutableOutcome):
        self.decorated.receiver_status(outcome)

    def failed_messages(self, outcome: IncrementMutableOutcome):
        self.decorated.failed_messages(outcome)

    def executed_messages(self, outcome: IncrementMutableOutcome):
        self.decorated.executed_messages(outcome)

    def hardware_connected(self, outcome: BinaryMutableOutcome):
        self.decorated.hardware_connected(outcome)

    def hardware_reloaded(self, outcome: BinaryMutableOutcome):
        self.decorated.hardware_reloaded(outcome)


class MetricFieldWrapper:
    def __init__(
        self,
        func: Callable,
        outcome: Union[IncrementMutableOutcome, BinaryMutableOutcome],
    ):
        self.callable = func
        self.outcome = outcome

    def __enter__(self):
        # Loan out the mutable outcome for change
        return self.outcome

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Apply the outcome to target callable
        try:
            self.callable(self.outcome)
        except Exception as ex:
            log.warning(f"Metric setting errored {str(ex)}")


class MetricExporter:
    """
    Factory for context managers for metrics reporting over different
    backend reporting frameworks

    Dynamically builds member functions that mirror the backend it is given.
    The Backend is the API specification.
    """

    def __init__(self, backend):
        if isinstance(backend, type):
            raise ValueError("Argument must be an instance not a type")
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
            except KeyError as ex:
                log.error(
                    f" An error occurred while processing "
                    f"the function's outcome parameter {ex}"
                )
                raise ex

        for func_name, func in methods:
            nargs = func.__code__.co_argcount
            if not nargs == 2:
                raise ValueError(
                    f"Receiver must have one non-self argument on each "
                    f"function. Found {nargs} while evaluating {func_name}"
                    f" on {str(type(backend))}"
                )
            # build no-arg setting functions on this matching backend public name
            setattr(self, func_name, decorate(func))
