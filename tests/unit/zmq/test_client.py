"""Unit tests for ZMQ client config normalisation."""

import pytest
from compiler_config.config import CompilerConfig

from qat_rpc.zmq.client import ZMQClient


class TestBuildConfig:
    def _build(self, config):
        """Call _build_config without connecting to a server."""
        return ZMQClient._build_config(None, config)

    def _config_json(self, repeats: int) -> str:
        config = CompilerConfig()
        config.repeats = repeats
        return config.to_json()

    def test_none_returns_default_json(self):
        result = self._build(None)
        expected = CompilerConfig().to_json()
        assert result == expected

    @pytest.mark.parametrize("repeats", [500, 42])
    def test_compiler_config_roundtrip(self, repeats):
        config = CompilerConfig()
        config.repeats = repeats
        result = self._build(config)
        roundtripped = CompilerConfig.create_from_json(result)
        assert roundtripped.repeats == repeats

    def test_string_normalisation(self):
        """Passing a JSON string re-parses and re-serialises for consistency."""
        json_str = self._config_json(repeats=123)
        result = self._build(json_str)
        # Round-tripped JSON should be equivalent
        assert CompilerConfig.create_from_json(result).to_json() == result
