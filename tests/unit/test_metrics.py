"""Unit tests for the metrics framework."""

import pytest

from qat_rpc.metrics import (
    BinaryMutableOutcome,
    IncrementMutableOutcome,
    MetricExporter,
)


class _FakeBinaryBackend:
    """Recording backend for binary outcome metrics."""

    def __init__(self):
        self.outcomes: list[BinaryMutableOutcome] = []

    def report(self, outcome: BinaryMutableOutcome):
        self.outcomes.append(outcome)


class _FakeIncrementBackend:
    """Recording backend for increment outcome metrics."""

    def __init__(self):
        self.outcomes: list[IncrementMutableOutcome] = []

    def report(self, outcome: IncrementMutableOutcome):
        self.outcomes.append(outcome)


class TestMetricExporterValidation:
    def test_rejects_type_instead_of_instance(self):
        with pytest.raises(TypeError):
            MetricExporter(_FakeBinaryBackend)

    def test_rejects_backend_with_too_many_args(self):
        class _TwoArgBackend:
            def report(self, one_arg, extra_arg): ...

        with pytest.raises(ValueError):
            MetricExporter(_TwoArgBackend())

    def test_rejects_backend_with_no_args(self):
        class _NoArgBackend:
            def report(self): ...

        with pytest.raises(ValueError):
            MetricExporter(_NoArgBackend())


class TestBinaryOutcomeContextManager:
    @pytest.fixture()
    def backend(self):
        return _FakeBinaryBackend()

    def test_success(self, backend):
        with MetricExporter(backend=backend).report() as metric:
            metric.succeed()

        assert len(backend.outcomes) == 1
        assert float(backend.outcomes[0]) == 1.0

    def test_failure(self, backend):
        with MetricExporter(backend=backend).report() as metric:
            metric.fail()

        assert len(backend.outcomes) == 1
        assert float(backend.outcomes[0]) == 0.0

    def test_defaults_to_failure(self, backend):
        with MetricExporter(backend=backend).report():
            ...

        assert len(backend.outcomes) == 1
        assert float(backend.outcomes[0]) == 0.0

    def test_failure_is_sticky(self, backend):
        with MetricExporter(backend=backend).report() as metric:
            metric.fail()
            metric.succeed()

        assert len(backend.outcomes) == 1
        assert float(backend.outcomes[0]) == 0.0


class TestIncrementOutcomeContextManager:
    @pytest.fixture()
    def backend(self):
        return _FakeIncrementBackend()

    def test_single_increment(self, backend):
        with MetricExporter(backend=backend).report() as metric:
            metric.increment()

        assert len(backend.outcomes) == 1
        outcome = backend.outcomes[0]
        assert float(outcome) == 1.0

    def test_multiple_increments(self, backend):
        with MetricExporter(backend=backend).report() as metric:
            for _ in range(5):
                metric.increment()

        assert len(backend.outcomes) == 1
        outcome = backend.outcomes[0]
        assert float(outcome) == 5.0


class TestBinaryMutableOutcome:
    def test_succeed_converts_to_numeric(self):
        outcome = BinaryMutableOutcome()
        outcome.succeed()
        assert float(outcome) == 1.0
        assert int(outcome) == 1

    def test_fail_converts_to_numeric(self):
        outcome = BinaryMutableOutcome()
        outcome.fail()
        assert float(outcome) == 0.0
        assert int(outcome) == 0


class TestIncrementMutableOutcome:
    def test_accumulates(self):
        outcome = IncrementMutableOutcome()
        for _ in range(5):
            outcome.increment()
        assert float(outcome) == 5.0
