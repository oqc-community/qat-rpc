import argparse
from pathlib import Path

from qat_rpc.zmq.wrappers import ZMQClient

parser = argparse.ArgumentParser(
    prog="QAT submission service", description="Submit your QASM or QIR program to QAT."
)
parser.add_argument("program", type=str, help="Program string or path to program file.")
parser.add_argument("--config", type=str, help="Serialised CompilerConfig json")


def qat_run():
    args = parser.parse_args()
    program = args.program
    config = args.config
    if Path(program).is_file():
        program = Path(program).read_text()
    if config is not None and Path(config).is_file():
        config = Path(config).read_text()
    zmq_client = ZMQClient()
    results = zmq_client.execute_task(program, config)
    print(results)
