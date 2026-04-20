# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023-2026 Oxford Quantum Circuits Ltd
"""Unit tests for ZMQ client config normalisation."""

import pytest
from compiler_config.config import CompilerConfig

from qat_rpc.zmq.client import ZMQClient


class TestBuildConfig:
    @staticmethod
    def _config(repeats: int) -> CompilerConfig:
        config = CompilerConfig()
        config.repeats = repeats
        return config

    def test_none_returns_default(self):
        result = ZMQClient._build_config(None)
        assert isinstance(result, CompilerConfig)
        assert result.to_json() == CompilerConfig().to_json()

    @pytest.mark.parametrize("repeats", [500, 42])
    def test_compiler_config_passthrough(self, repeats):
        config = self._config(repeats)
        result = ZMQClient._build_config(config)
        assert isinstance(result, CompilerConfig)
        assert result.repeats == repeats

    def test_string_normalisation(self):
        """Passing a JSON string parses into a CompilerConfig."""
        config = self._config(repeats=123)
        result = ZMQClient._build_config(config.to_json())
        assert isinstance(result, CompilerConfig)
        assert result.repeats == 123
