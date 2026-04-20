# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023-2026 Oxford Quantum Circuits Ltd
"""Unit tests for the qat_rpc package root."""

from importlib.metadata import version

from qat_rpc import __version__


class TestVersion:
    def test_version_is_string(self):
        assert isinstance(__version__, str)

    def test_version_matches_metadata(self):
        assert __version__ == version("qat-rpc")

    def test_version_is_not_unknown(self):
        assert __version__ != "unknown"
