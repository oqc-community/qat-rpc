# QAT-RPC

ZeroMQ-based RPC tooling for the OQC [QAT](https://oqc-community.github.io/qat/main/index.html)
(Quantum Assembly Toolchain) compiler and runtime. Enables remote execution of
quantum programs (OpenQASM / QIR) through a client-server architecture with
Prometheus metrics export.

## Quick start

### Starting the server

```bash
# In development (with Poetry)
poetry run qat_server

# Or directly via Python module
poetry run python -m qat_rpc.zmq.server

# After pip install (system-wide)
qat_server
```

The server is configured through environment variables:

| Variable | Description | Default |
| --- | --- | --- |
| `RECEIVER_PORT` | ZMQ server port | `5556` |
| `METRICS_PORT` | Prometheus exporter port | `9250` |
| `QAT_CONFIG_PATH` | Path to QAT config file | None - runs in echo mode |

### Using the client

```python
from qat_rpc.zmq import ZMQClient

client = ZMQClient()

# Compile and execute a program
results = client.execute_task(program, config)

# Or compile and execute separately
compiled = client.compile_program(program, config)
results = client.execute_compiled(compiled["package"], config)

# Query hardware information
version = client.api_version()
couplings = client.qpu_couplings()
```

### CLI

```bash
# In development (with Poetry)
poetry run qat_comexe path/to/program.qasm --config '{"repeats": 100}'

# After pip install
qat_comexe path/to/program.qasm --config '{"repeats": 100}'

# QIR text or binary bitcode
poetry run qat_comexe path/to/program.ll
poetry run qat_comexe path/to/program.bc

# Pass a program string directly
poetry run qat_comexe "OPENQASM 2.0; ..." --host 192.168.1.10 --port 5556
```

## Installation

We use [Poetry](https://python-poetry.org/) for dependency management and require
[Python 3.10+](https://www.python.org/downloads/).

```bash
poetry install
```

## Development

### Running checks

All checks are managed via [Poe the Poet](https://poethepoet.naez.com/):

```bash
# Run all checks (format, lint, types, deps, licenses, vuln, test)
poetry run poe checks

# Individual tasks
poetry run poe format    # check formatting
poetry run poe lint      # ruff linting
poetry run poe types     # pyright type checking
poetry run poe test      # run tests
poetry run poe deps      # deptry + import-linter
poetry run poe vuln      # bandit + pip-audit

# Auto-fix formatting and lint issues
poetry run poe fix
```

### Contributing

To take the first steps towards contributing to QAT-RPC, visit our
[contribution](https://github.com/oqc-community/qat-rpc/blob/main/CONTRIBUTING.rst)
documents, which provides details about our process.

We also encourage new contributors to familiarise themselves with the
[code of conduct](https://github.com/oqc-community/qat-rpc/blob/main/CODE_OF_CONDUCT.rst)
and to adhere to these expectations.

### Assistance

For support, please reach out in the
[discussions](https://github.com/oqc-community/qat-rpc/discussions) tab of this
repository or file an [issue](https://github.com/oqc-community/qat-rpc/issues).

## Licence

This code in this repository is licensed under the BSD 3-Clause Licence.
Please see [LICENSE](https://github.com/oqc-community/qat-rpc/blob/main/LICENSE)
for more information.

## Feedback

Please let us know your feedback and any suggestions by reaching out in
[Discussions](https://github.com/oqc-community/qat-rpc/discussions).
Additionally, to report any concerns or
[code of conduct](https://github.com/oqc-community/qat-rpc/blob/main/CODE_OF_CONDUCT.rst)
violations please use this
[form](https://docs.google.com/forms/d/e/1FAIpQLSeyEX_txP3JDF3RQrI3R7ilPHV9JcZIyHPwLLlF6Pz7iGnocw/viewform?usp=sf_link).
