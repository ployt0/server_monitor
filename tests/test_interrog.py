import datetime
from unittest.mock import patch, sentinel, Mock

import requests
from requests.exceptions import SSLError

from indie_gen_funcs import DAY_TIME_FMT, ResultHolder, ErrorHandler
from interrog_routines import interrog_routine


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




@patch("interrog_routines.CheckResult", autospec=True)
@patch.object(requests, "get", autospec=True)
@patch("interrog_routines.SSHInterrogator.do_queries", autospec=True)
def test_interrog_routine(mock_queries, mock_get, mock_check_result):
    mock_http_response_time = 0.0421
    sample_latencies = ['16.0', '15.0', '18.0', '16.0']
    configure_mock_get(mock_get, mock_http_response_time)
    err_handler, result_holder = get_interrog_mock_args()
    ave_latency, max_latency = get_ave_max_latencies(sample_latencies)
    interrog_routine(
        err_handler,
        {"home_page": sentinel.home_page},
        result_holder, sentinel.ipv4, sample_latencies)
    mock_check_result.assert_called_once_with(
        result_holder.time.strftime(DAY_TIME_FMT), sentinel.ipv4,
        ave_latency, max_latency,
        str(int(round(1000 * mock_http_response_time))),
        str(mock_get.return_value.status_code), None, None,
        None, None, None, None)
    mock_queries.assert_called_once()
    mock_get.assert_called_once_with(sentinel.home_page, timeout=5, verify=True)


@patch("interrog_routines.CheckResult", autospec=True)
@patch.object(requests, "get", autospec=True)
@patch("interrog_routines.SSHInterrogator.do_queries", autospec=True)
def test_self_sign_interrog_routine(mock_queries, mock_get, mock_check_result):
    mock_http_response_time = 0.0421
    sample_latencies = ['16.0', '15.0', '18.0', '16.0']
    configure_mock_get(mock_get, mock_http_response_time)
    err_handler, result_holder = get_interrog_mock_args()
    interrog_routine(
        err_handler,
        {"home_page": sentinel.home_page, "verify": sentinel.vrfy_path},
        result_holder, sentinel.ipv4, sample_latencies)
    mock_check_result.assert_called_once()
    mock_queries.assert_called_once()
    mock_get.assert_called_once_with(
        sentinel.home_page, timeout=5, verify=sentinel.vrfy_path)


@patch("interrog_routines.CheckResult", autospec=True)
@patch.object(requests, "get", autospec=True, side_effect=[
    SSLError(), Mock(ok=True, status_code=200, elapsed=Mock(total_seconds=lambda:200))])
@patch("interrog_routines.SSHInterrogator.do_queries", autospec=True)
def test_interrog_routine_when_cert_expired(mock_queries, mock_get, mock_check_result):
    sample_latencies = ['16.0', '15.0', '18.0', '16.0']
    # configure_mock_get(mock_get, mock_http_response_time)
    err_handler, result_holder = get_interrog_mock_args()
    interrog_routine(
        err_handler,
        {"home_page": sentinel.home_page},
        result_holder, sentinel.ipv4, sample_latencies)
    mock_check_result.assert_called_once()
    assert mock_get.call_count == 2
    mock_queries.assert_called_once()
    err_handler.append.assert_called_once()


@patch("interrog_routines.CheckResult", autospec=True)
@patch.object(requests, "get", autospec=True, side_effect=requests.exceptions.ConnectionError())
@patch("interrog_routines.SSHInterrogator.do_queries", autospec=True)
def test_interrog_routine_when_server_unresponsive(mock_queries, mock_get, mock_check_result):
    sample_latencies = ['16.0', '15.0', '18.0', '16.0']
    err_handler, result_holder = get_interrog_mock_args()
    interrog_routine(
        err_handler,
        {"home_page": sentinel.home_page},
        result_holder, sentinel.ipv4, sample_latencies)
    mock_check_result.assert_not_called()
    mock_get.assert_called_once()
    mock_queries.assert_not_called()
    err_handler.append.assert_called_once_with(mock_get.side_effect)
