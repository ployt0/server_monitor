import subprocess
from unittest.mock import Mock, patch, sentinel

from generalised_functions import ErrorHandler
from ping_functions import ping, get_ping_latencies

STDOUT_WINDOWS_ONLINE = \
    b'\r\nPinging 8.8.8.8 with 32 bytes of data:\r\nReply from 8.8.8.8: bytes=32 time=16ms TTL=119\r\nReply from ' \
    b'8.8.8.8: bytes=32 time=15ms TTL=119\r\nReply from 8.8.8.8: bytes=32 time=18ms TTL=119\r\nReply from 8.8.8.8: ' \
    b'bytes=32 time=16ms TTL=119\r\n\r\nPing statistics for 8.8.8.8:\r\n    Packets: Sent = 4, Received = 4, ' \
    b'Lost = 0 (0% loss),\r\nApproximate round trip times in milli-seconds:\r\n    Minimum = 15ms, Maximum = 18ms, ' \
    b'Average = 16ms\r\n '

STDOUT_WINDOWS_FAILURE = \
    b'\r\nPinging 248.248.128.128 with 32 bytes of data:\r\nPING: transmit failed. General failure. \r\nPING: ' \
    b'transmit failed. General failure. \r\nPING: transmit failed. General failure. \r\nPING: transmit failed. ' \
    b'General failure. \r\n\r\nPing statistics for 248.248.128.128:\r\n    Packets: Sent = 4, Received = 0, ' \
    b'Lost = 4 (100% loss),\r\n '

STDOUT_WINDOWS_OFFLINE = \
    b'\r\nPinging 8.8.8.8 with 32 bytes of data:\r\nReply from 192.168.0.2: Destination host unreachable.\r\nReply ' \
    b'from 192.168.0.2: Destination host unreachable.\r\nReply from 192.168.0.2: Destination host ' \
    b'unreachable.\r\nReply from 192.168.0.2: Destination host unreachable.\r\n\r\nPing statistics for 8.8.8.8:\r\n   ' \
    b' Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),\r\n '

STDOUT_LINUX_ONLINE = \
    b'\nPING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.\n64 bytes from 8.8.8.8: icmp_seq=1 ttl=119 time=7.51 ms\n64 ' \
    b'bytes from 8.8.8.8: icmp_seq=2 ttl=119 time=7.63 ms\n64 bytes from 8.8.8.8: icmp_seq=3 ttl=119 time=7.68 ms\n64 ' \
    b'bytes from 8.8.8.8: icmp_seq=4 ttl=119 time=7.46 ms\n\n--- 8.8.8.8 ping statistics ---\n4 packets transmitted, ' \
    b'4 received, 0% packet loss, time 3006ms\nrtt min/avg/max/mdev = 7.463/7.570/7.679/0.088 ms\n '

STDOUT_LINUX_FAILURE = \
    b'\nPING 248.248.128.128 (248.248.128.128) 56(84) bytes of data.\nFrom 192.168.0.1 icmp_seq=2 Redirect Host(New ' \
    b'nexthop: 128.128.248.248)\nFrom 192.168.0.1 icmp_seq=3 Redirect Host(New nexthop: 128.128.248.248)\nFrom ' \
    b'192.168.0.1 icmp_seq=4 Destination Host Unreachable\n\n--- 248.248.128.128 ping statistics ---\n4 packets ' \
    b'transmitted, 0 received, +3 errors, 100% packet loss, time 3080ms\n\n '


@patch("ping_functions.subprocess.run", return_value=Mock(
    subprocess.CompletedProcess,
    returncode=0,
    stdout=STDOUT_WINDOWS_OFFLINE))
@patch("ping_functions.platform.system", return_value="windows")
def test_ping_offline_windows(mock_system, mock_run):
    result = ping("8.8.8.8")
    mock_run.assert_called_once_with(
        ['ping', '-n', '4', "8.8.8.8"], capture_output=True)
    mock_system.assert_called_once_with()
    assert result.stdout == STDOUT_WINDOWS_OFFLINE


@patch("ping_functions.subprocess.run", return_value=Mock(
    subprocess.CompletedProcess,
    returncode=0,
    stdout=STDOUT_WINDOWS_ONLINE))
@patch("ping_functions.platform.system", return_value="windows")
def test_ping_online_windows(mock_system, mock_run):
    result = ping("8.8.8.8")
    mock_run.assert_called_once_with(
        ['ping', '-n', '4', "8.8.8.8"], capture_output=True)
    mock_system.assert_called_once_with()
    assert result.stdout == STDOUT_WINDOWS_ONLINE


@patch("ping_functions.subprocess.run", return_value=Mock(
    subprocess.CompletedProcess,
    returncode=1,
    stdout=STDOUT_WINDOWS_FAILURE))
@patch("ping_functions.platform.system", return_value="windows")
def test_ping_failure_windows(mock_system, mock_run):
    result = ping("248.248.128.128")
    mock_run.assert_called_once_with(
        ['ping', '-n', '4', "248.248.128.128"], capture_output=True)
    mock_system.assert_called_once_with()
    assert result.stdout == STDOUT_WINDOWS_FAILURE


@patch("ping_functions.subprocess.run", return_value=Mock(
    subprocess.CompletedProcess,
    returncode=0,
    stdout=STDOUT_LINUX_ONLINE))
@patch("ping_functions.platform.system", return_value="linux")
def test_ping_online_linux(mock_system, mock_run):
    result = ping("8.8.8.8")
    mock_run.assert_called_once_with(
        ['ping', '-c', '4', "8.8.8.8"], capture_output=True)
    mock_system.assert_called_once_with()
    assert result.stdout == STDOUT_LINUX_ONLINE


@patch("ping_functions.subprocess.run", return_value=Mock(
    subprocess.CompletedProcess,
    returncode=1,
    stdout=STDOUT_LINUX_FAILURE))
@patch("ping_functions.platform.system", return_value="linux")
def test_ping_failure_linux(mock_system, mock_run):
    result = ping("248.248.128.128")
    mock_run.assert_called_once_with(
        ['ping', '-c', '4', "248.248.128.128"], capture_output=True)
    mock_system.assert_called_once_with()
    assert result.stdout == STDOUT_LINUX_FAILURE


@patch("ping_functions.ping", return_value=Mock(
    subprocess.CompletedProcess,
    returncode=0,
    stdout=STDOUT_LINUX_ONLINE))
def test_get_ping_latencies_linux(mock_ping):
    error_handler = ErrorHandler()
    latencies = get_ping_latencies(error_handler, sentinel.ip_addy)
    mock_ping.assert_called_once_with(sentinel.ip_addy)
    assert len(latencies) == 4
    assert list(map(float, latencies)) == [7.51, 7.63, 7.68, 7.46]


@patch("ping_functions.ping", return_value=Mock(
    subprocess.CompletedProcess,
    returncode=1,
    stdout=STDOUT_LINUX_FAILURE))
def test_get_ping_latencies_linux_failure(mock_ping):
    error_handler = ErrorHandler()
    latencies = get_ping_latencies(error_handler, sentinel.ip_addy)
    mock_ping.assert_called_once_with(sentinel.ip_addy)
    assert len(latencies) == 0


@patch("ping_functions.ping", return_value=Mock(
    subprocess.CompletedProcess,
    returncode=0,
    stdout=STDOUT_WINDOWS_ONLINE))
def test_get_ping_latencies_windows(mock_ping):
    error_handler = ErrorHandler()
    latencies = get_ping_latencies(error_handler, sentinel.ip_addy)
    mock_ping.assert_called_once_with(sentinel.ip_addy)
    assert len(latencies) == 4
    assert list(map(float, latencies)) == [16.0, 15.0, 18.0, 16.0]


@patch("ping_functions.ping", return_value=Mock(
    subprocess.CompletedProcess,
    returncode=1,
    stdout=STDOUT_WINDOWS_FAILURE))
def test_get_ping_latencies_windows_failure(mock_ping):
    error_handler = ErrorHandler()
    latencies = get_ping_latencies(error_handler, sentinel.ip_addy)
    mock_ping.assert_called_once_with(sentinel.ip_addy)
    assert len(latencies) == 0
