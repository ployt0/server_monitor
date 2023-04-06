from unittest.mock import patch, sentinel

from check_result import deserialise_simple_csv, CheckResult


def test_deserialise_simple_csv():
    csv_list = deserialise_simple_csv("yolo,barry white,george soros,tilda swinton,None,bill gates")
    assert csv_list == ['yolo', 'barrywhite', 'george soros', 'tilda swinton', None, 'bill gates']


@patch("check_result.format_ipv4", return_value="yarp!")
def test_check_result(mock_format_ipv4):
    res = CheckResult(sentinel.time, sentinel.ipv4, sentinel.ping, sentinel.ping_max,
                      sentinel.http_rtt, sentinel.http_code, sentinel.mem_avail, sentinel.swap_free,
                      sentinel.disk_avail, sentinel.last_boot, sentinel.ports, sentinel.peers)
    assert len(res.get_header().split(",")) == 12
    mock_format_ipv4.assert_not_called()
    assert len(res.to_csv().split(",")) == 12
    mock_format_ipv4.assert_called_once_with(sentinel.ipv4)
    assert res.get_unit_name() == "node"
