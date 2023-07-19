import datetime
from unittest.mock import Mock

from generalised_functions import ResultHolder
from indie_gen_funcs import ErrorHandler


def configure_mock_get(mock_get, mock_http_response_time):
    mock_get.return_value.elapsed.total_seconds.return_value = mock_http_response_time
    mock_get.return_value.ok = True
    mock_get.return_value.status_code = 200


def get_interrog_mock_args():
    result_holder = Mock(ResultHolder, time=datetime.datetime.utcnow())
    err_handler = Mock(ErrorHandler)
    return err_handler, result_holder


def get_ave_max_latencies(latencies):
    latencies = list(map(float, latencies))
    ave_latency = str(int(round(sum(latencies) / len(latencies))))
    max_latency = str(int(round(max(latencies))))
    return ave_latency, max_latency





