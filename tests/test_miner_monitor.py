import datetime
from unittest.mock import patch, sentinel, Mock

from generalised_functions import ResultHolder, ErrorHandler, DAY_TIME_FMT
from miner_monitor import CheckResult, interrog_routine, display_opt_int_list


@patch("miner_monitor.format_ipv4", return_value="yarp!")
def test_CheckResult(mock_format_ipv4):
    res = CheckResult(sentinel.time, sentinel.ipv4, sentinel.ping, sentinel.ping_max,
                      sentinel.mem_avail, sentinel.disk_avail, sentinel.last_boot, sentinel.ports,
                      sentinel.peers)
    assert len(res.get_header().split(",")) == 11
    mock_format_ipv4.assert_not_called()
    assert len(res.to_csv().split(",")) == 11
    mock_format_ipv4.assert_called_once_with(sentinel.ipv4)
    assert res.get_unit_name() == "miner"


@patch("miner_monitor.CheckResult", autospec=True)
@patch("miner_monitor.MinerInterrogator.do_queries", autospec=True)
def test_interrog_routine(mock_queries, mock_check_result):
    result_holder = Mock(ResultHolder, time=datetime.datetime.utcnow())
    err_handler = Mock(ErrorHandler)
    sample_latencies = ['16.0', '15.0', '18.0', '16.0']
    ave_latency = str(int(round(sum(map(float, sample_latencies)) / len(sample_latencies))))
    max_latency = str(int(round(max(map(float, sample_latencies)))))
    interrog_routine(err_handler, {}, result_holder, sentinel.ipv4, sample_latencies)
    mock_check_result.assert_called_once_with(
        result_holder.time.strftime(DAY_TIME_FMT), sentinel.ipv4, ave_latency, max_latency,
        None, None, None, None, None, None, None)
    mock_queries.assert_called_once()


def test_display_opt_int_list():
    assert display_opt_int_list([None] * 4) is None
    assert display_opt_int_list(["42"] * 4) == "42_42_42_42"
    assert display_opt_int_list(["42", None, "42", None]) == "42_None_42_None"
