import os
from pathlib import Path
from signal import SIGINT, SIGTERM, signal

from qat.purr.compiler.devices import Calibratable
from qat.purr.utils.logger import get_default_logger

from qat_rpc.utils.constants import PROMETHEUS_PORT
from qat_rpc.utils.metrics import MetricExporter, PrometheusReceiver
from qat_rpc.zmq.wrappers import ZMQServer

log = get_default_logger()


class GracefulKill:
    def __init__(self, receiver: ZMQServer):
        signal(SIGINT, self._sigint)
        signal(SIGTERM, self._sigterm)
        self.receiver = receiver

    def _sigint(self, *args):
        self.receiver.stop()

    def _sigterm(self, *args):
        self.receiver.stop()


def main():
    hw = None
    metric_exporter = MetricExporter(backend=PrometheusReceiver(PROMETHEUS_PORT))
    if (calibration_file := os.getenv("TOSHIKO_CAL")) is not None:
        calibration_file = Path(calibration_file)
        if not calibration_file.is_absolute() and not calibration_file.is_file():
            calibration_file = Path(Path(__file__).parent, calibration_file)
        if not calibration_file.is_file():
            raise ValueError(f"No such file: {calibration_file}")
        log.info(f"Loading: {calibration_file} ")
        hw = Calibratable.load_calibration_from_file(str(calibration_file))
        log.debug("Loaded")

    receiver = ZMQServer(hardware=hw, metric_exporter=metric_exporter)
    gk = GracefulKill(receiver)

    log.info(f"Starting receiver with {type(receiver._hardware)} hardware.")
    receiver.run()


if __name__ == "__main__":
    main()
