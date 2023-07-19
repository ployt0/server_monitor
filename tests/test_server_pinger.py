import datetime
import subprocess
from unittest.mock import patch, sentinel, Mock, mock_open, call

from indie_gen_funcs import RESULTS_DIR
from server_pinger import time_pings, ping_all_day, PingResult, save_days_pings

PING_OUTPUT = \
    b'\nPING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.\n64 bytes from 8.8.8.8: icmp_seq=1 ttl=119 time=7.51 ms\n64 ' \
    b'bytes from 8.8.8.8: icmp_seq=2 ttl=119 time=7.63 ms\n64 bytes from 8.8.8.8: icmp_seq=3 ttl=119 time=7.68 ms\n64 ' \
    b'bytes from 8.8.8.8: icmp_seq=4 ttl=119 time=7.46 ms\n\n--- 8.8.8.8 ping statistics ---\n4 packets transmitted, ' \
    b'4 received, 0% packet loss, time 3006ms\nrtt min/avg/max/mdev = 7.463/7.570/7.679/0.088 ms\n '


@patch("server_pinger.ping", return_value=Mock(
    subprocess.CompletedProcess,
    returncode=0,
    stdout=PING_OUTPUT))
def test_time_pings(mock_ping):
    ave_latency_ms, max_latency_ms = time_pings(sentinel.ip_addy)
    assert ave_latency_ms == 8
    assert max_latency_ms == 8
    mock_ping.assert_called_once_with(sentinel.ip_addy)


EXPECTED_PINGS = [
    PingResult(local_time='000113 13:30:00', ipv4='mock_ip1', ave_latency_ms=15, max_latency_ms=19),
    PingResult(local_time='000113 13:30:00', ipv4='mock_ip2', ave_latency_ms=15, max_latency_ms=19),
    PingResult(local_time='000114 13:30:00', ipv4='mock_ip1', ave_latency_ms=15, max_latency_ms=19),
    PingResult(local_time='000114 13:30:00', ipv4='mock_ip2', ave_latency_ms=15, max_latency_ms=19),
]


@patch("server_pinger.save_days_pings", autospec=True, return_value=())
@patch("server_pinger.time_pings", autospec=True, return_value=(15, 19))
@patch("server_pinger.time", autospec=True)
@patch("server_pinger.datetime", spec=datetime)
def test_ping_all_day(mock_datetime, mock_time, mock_time_pings, save_days_pings):
    mock_datetime.utcnow = Mock(
        side_effect=[datetime.datetime(2000, 1, 13, 13, 30, 00)] * 5 +
                    [datetime.datetime(2000, 1, 14, 13, 30, 00)] * 5
    )
    ping_all_day(["mock_ip1", "mock_ip2"])
    save_days_pings.assert_called_once_with(EXPECTED_PINGS, '000113')


def test_save_days_pings():
    with patch("builtins.open", mock_open()) as mocked_open:
        save_days_pings(EXPECTED_PINGS, '000113')
        mocked_open.assert_called_once_with("{}/pings_{}.csv".format(RESULTS_DIR, '000113'), "a+")
        # Note that calls continue into the next day if pinging delays them that much.
        mocked_open.return_value.write.assert_has_calls([
            call('000113 13:30:00,mock_ip1,15,19\n'),
            call('000113 13:30:00,mock_ip2,15,19\n'),
            call('000114 13:30:00,mock_ip1,15,19\n'),
            call('000114 13:30:00,mock_ip2,15,19\n')
        ])
