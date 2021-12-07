import datetime
from unittest.mock import patch, sentinel, Mock

from generalised_functions import ResultHolder, ErrorHandler, DAY_TIME_FMT
from server_mon import CheckResult, interrog_routine


@patch("server_mon.format_ipv4", return_value="yarp!")
def test_CheckResult(mock_format_ipv4):
    res = CheckResult(sentinel.time, sentinel.ipv4, sentinel.ping, sentinel.ping_max,
                      sentinel.http_rtt, sentinel.http_code, sentinel.mem_avail, sentinel.swap_free,
                      sentinel.disk_avail, sentinel.last_boot, sentinel.ports, sentinel.peers)
    assert len(res.get_header().split(",")) == 12
    mock_format_ipv4.assert_not_called()
    assert len(res.to_csv().split(",")) == 12
    mock_format_ipv4.assert_called_once_with(sentinel.ipv4)
    assert res.get_unit_name() == "node"


@patch("server_mon.CheckResult", autospec=True)
@patch("server_mon.requests.get", autospec=True)
@patch("server_mon.SSHInterrogator.do_queries", autospec=True)
def test_interrog_routine(mock_queries, mock_get, mock_check_result):
    mock_http_response_time = 0.0421
    mock_get.return_value.elapsed.total_seconds.return_value = mock_http_response_time
    mock_get.return_value.ok = True
    mock_get.return_value.status_code = 200
    result_holder = Mock(ResultHolder, time=datetime.datetime.utcnow())
    err_handler = Mock(ErrorHandler)
    sample_latencies = ['16.0', '15.0', '18.0', '16.0']
    ave_latency = str(int(round(sum(map(float, sample_latencies)) / len(sample_latencies))))
    max_latency = str(int(round(max(map(float, sample_latencies)))))
    interrog_routine(err_handler, {}, result_holder, sentinel.ipv4, sample_latencies)
    mock_check_result.assert_called_once_with(
        result_holder.time.strftime(DAY_TIME_FMT), sentinel.ipv4, ave_latency, max_latency,
        str(int(round(1000 * mock_http_response_time))), str(mock_get.return_value.status_code), None, None,
        None, None, None, None)
    mock_queries.assert_called_once()
    mock_get.assert_called_once_with("http://sentinel.ipv4", timeout=5)
