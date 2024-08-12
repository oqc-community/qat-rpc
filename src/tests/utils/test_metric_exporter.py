import abc
from unittest.mock import Mock

import pytest

from qat_rpc.utils.metrics import (
    BinaryMutableOutcome,
    IncrementMutableOutcome,
    MetricExporter,
    ReceiverAdapter,
    ReceiverBackend,
)


class Backend(abc.ABC):
    @abc.abstractmethod
    def report(self, outcome: BinaryMutableOutcome): ...


class BackendAdapter(Backend):
    def __init__(self, decorated):
        super(BackendAdapter, self).__init__()
        self.decorated = decorated

    def report(self, outcome: BinaryMutableOutcome):
        self.decorated.report(outcome)


@pytest.fixture
def mock_backend():
    return BackendAdapter(Mock(Backend))


@pytest.fixture
def mock_increment_backend():
    return ReceiverAdapter(Mock(ReceiverBackend))


def test_metric_exporter_aborts_if_given_type():
    with pytest.raises(ValueError):
        MetricExporter(BackendAdapter)  # Type not instance


def test_metric_exporter_aborts_if_interface_doesnt_match_one_arg_function():
    class BrokenBackendTwoArgFunc:
        def report(self, one_arg, extra_arg): ...

    with pytest.raises(ValueError):
        MetricExporter(BrokenBackendTwoArgFunc())

    class BrokenBackendOneArgFunc:
        def report(self): ...

    with pytest.raises(ValueError):
        MetricExporter(BrokenBackendOneArgFunc())


def test_metric_exporter_context_manager_with_success(mock_backend):
    with MetricExporter(backend=mock_backend).report() as metric:
        metric.succeed()

    mock_backend.decorated.report.assert_called_once_with(True)


def test_metric_exporter_context_manager_with_failure(mock_backend):
    with MetricExporter(backend=mock_backend).report() as metric:
        metric.fail()

    mock_backend.decorated.report.assert_called_once_with(False)


def test_metric_exporter_context_manager_with_default_failure(mock_backend):
    with MetricExporter(backend=mock_backend).report():
        ...

    mock_backend.decorated.report.assert_called_once_with(False)


def test_metric_exporter_context_manager_with_sticky_false(mock_backend):
    with MetricExporter(backend=mock_backend).report() as metric:
        metric.fail()
        metric.succeed()

    mock_backend.decorated.report.assert_called_once_with(False)


def test_increment_metric_exporter_single_increment(mock_increment_backend):
    with MetricExporter(backend=mock_increment_backend).failed_messages() as metric:
        metric.increment()
    expected_increment_outcome = mock_increment_backend.decorated.failed_messages.call_args[
        0
    ][0]
    assert float(expected_increment_outcome) == 1.0
    mock_increment_backend.decorated.failed_messages.assert_called_once_with(
        expected_increment_outcome
    )


def test_increment_metric_exporter_multiple_increment(mock_increment_backend):
    with MetricExporter(backend=mock_increment_backend).failed_messages() as metric:
        for _ in range(5):
            metric.increment()
    assert float(mock_increment_backend.decorated.failed_messages.call_args[0][0]) == 5.0


def test_implicit_conversion_of_proxy_object():
    outcome = BinaryMutableOutcome()
    outcome.succeed()
    assert float(outcome) == 1.0
    assert int(outcome) == 1

    outcome.fail()
    assert float(outcome) == 0.0
    assert int(outcome) == 0


def test_increment_outcome():
    outcome = IncrementMutableOutcome()
    for i in range(5):
        outcome.increment()
    assert float(outcome) == 5
