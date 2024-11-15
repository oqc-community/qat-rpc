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
    receiver_port = os.getenv("RECEIVER_PORT")
    metrics_port = os.getenv("METRICS_PORT")

    if receiver_port is not None:
        try:
            int(receiver_port)
        except ValueError:
            log.warning("Configured receiver port is not a valid integer.")
            receiver_port = 5556
            log.info(f"Defaulting receiver to run on port {receiver_port}")
        else:
            try:
                if not (1024 < int(receiver_port) < 49152):
                    raise ValueError(
                        "Receiver must be configured to run on a valid port number between 1024 and 49152."
                    )
                log.info(f"Receiver server is configured to start on port {receiver_port}.")
            except ValueError as e:
                log.warning(f"{e}")
                receiver_port = 5556
                log.info(f"Defaulting receiver to run on port {receiver_port}.")
    else:
        receiver_port = 5556

    if metrics_port is not None:
        try:
            int(metrics_port)
        except ValueError:
            log.warning("Configured metrics port is not a valid integer.")
            metrics_port = PROMETHEUS_PORT
            log.info(f"Defaulting metrics exporter to run on port {metrics_port}")
        else:
            try:
                if int(metrics_port) == int(receiver_port):
                    raise ValueError(
                        f"Metrics exporter cannot run on port {metrics_port}, it must be set to a different value to the receiver port."
                    )
                elif not (1024 < int(metrics_port) < 49152):
                    raise ValueError(
                        "Metrics exporter must be configured to run on a valid port number between 1024 and 49152."
                    )
                log.info(f"Metrics exporter is configured to start on port {metrics_port}.")
            except ValueError as e:
                log.warning(f"{e}")
                metrics_port = PROMETHEUS_PORT
                log.info(f"Defaulting metrics exporter to run on port {metrics_port}.")
    else:
        metrics_port = PROMETHEUS_PORT

    try:
        if int(metrics_port) == int(receiver_port):
            raise ValueError
    except ValueError:
        log.warning(
            "The receiver and metrics exporter have been configured to run on the same port."
        )
        receiver_port = 5556
        metrics_port = PROMETHEUS_PORT
        log.info(
            f"Defaulting receiver to run on port {receiver_port} and metrics exporter to run on port {metrics_port}."
        )

    metric_exporter = MetricExporter(backend=PrometheusReceiver(port=int(metrics_port)))

    if (calibration_file := os.getenv("TOSHIKO_CAL")) is not None:
        calibration_file = Path(calibration_file)
        if not calibration_file.is_absolute() and not calibration_file.is_file():
            calibration_file = Path(Path(__file__).parent, calibration_file)
        if not calibration_file.is_file():
            raise ValueError(f"No such file: {calibration_file}")
        log.info(f"Loading: {calibration_file} ")
        hw = Calibratable.load_calibration_from_file(str(calibration_file))
        log.debug("Loaded")

    receiver = ZMQServer(
        hardware=hw, server_port=receiver_port, metric_exporter=metric_exporter
    )
    gk = GracefulKill(receiver)

    log.info(
        f"Starting QAT receiver on port {str(receiver._port)} with {type(receiver._hardware)} hardware."
    )
    receiver.run()


if __name__ == "__main__":
    main()
