from typing import List
from unittest.mock import patch, Mock, sentinel, call

import pytest
from paramiko.channel import ChannelFile
from paramiko.client import SSHClient
from paramiko.pkey import PKey
from paramiko.ssh_exception import AuthenticationException, BadHostKeyException

import generalised_functions
from paramiko_client import SSHInterrogator, MinerInterrogator

SENTINEL_ERROR = RuntimeError("test injected")


@patch("server_mon.ErrorHandler", autospec=True)
def test_parse_user_csv(mock_error_handler):
    interrogator = SSHInterrogator(mock_error_handler)
    assert interrogator.parse_user_csv("forty,five") == {"forty", "five"}
    assert interrogator.parse_user_csv("fortyfive") == {"fortyfive"}
    assert interrogator.parse_user_csv("") == {""}


def patch_interrogator_client(interrogator: SSHInterrogator, mock_lines: List[str]) -> None:
    """Patch interrogator to return given lines."""
    mock_readlines = Mock(return_value=mock_lines)
    mock_channel_file = Mock(spec=ChannelFile, readlines=mock_readlines)
    mock_exec_command = Mock(autospec=True, return_value=(sentinel, mock_channel_file, sentinel))
    interrogator.client = Mock(spec=SSHClient, exec_command=mock_exec_command)


def mk_interrogator(mock_error_handler, mock_lines, side_effect=None):
    """Make/mock interrogator with optional error injection."""
    interrogator = SSHInterrogator(mock_error_handler)
    patch_interrogator_client(interrogator, mock_lines)
    if side_effect:
        interrogator.client.exec_command.side_effect = side_effect
    return interrogator


@patch("server_mon.ErrorHandler", autospec=True)
def test_query_ports_unknown(mock_error_handler, ss_lines_1):
    interrogator = mk_interrogator(mock_error_handler, ss_lines_1)
    interrogator.query_ports(set())
    assert interrogator.ports == "22"
    mock_error_handler.append.assert_not_called()


@patch("server_mon.ErrorHandler", autospec=True)
def test_query_ports_known(mock_error_handler, ss_lines_1):
    interrogator = mk_interrogator(mock_error_handler, ss_lines_1)
    interrogator.query_ports({"22"})
    assert interrogator.ports == ""
    mock_error_handler.append.assert_not_called()


@patch("server_mon.ErrorHandler", autospec=True)
def test_query_ports_fail(mock_error_handler, ss_lines_1):
    interrogator = mk_interrogator(mock_error_handler, ss_lines_1, SENTINEL_ERROR)
    interrogator.query_ports({"22"})
    mock_error_handler.append.assert_called_once_with(SENTINEL_ERROR)


@patch("server_mon.ErrorHandler", autospec=True)
@patch("paramiko_client.SSHInterrogator.initialise_connection", return_value=None)
@patch("paramiko_client.SSHInterrogator.remote_tentative_calls")
def test_do_queries(mock_remote_tentative_calls, mock_initialise_connection, mock_error_handler, mock_rmt_pc_1):
    interrogator = SSHInterrogator(mock_error_handler)
    interrogator.do_queries(mock_rmt_pc_1)
    mock_initialise_connection.assert_called_once_with(mock_rmt_pc_1["ip"], mock_rmt_pc_1["creds"])
    mock_remote_tentative_calls.assert_called_once_with(mock_rmt_pc_1)


@patch("server_mon.ErrorHandler", autospec=True)
@patch("paramiko_client.SSHInterrogator.initialise_connection", return_value=None)
@patch("paramiko_client.SSHInterrogator.remote_tentative_calls", side_effect=SENTINEL_ERROR)
def test_do_queries_throwing(mock_remote_tentative_calls, mock_initialise_connection, mock_error_handler, mock_rmt_pc_1):
    interrogator = SSHInterrogator(mock_error_handler)
    interrogator.do_queries(mock_rmt_pc_1)
    mock_error_handler.append.assert_called_once_with(SENTINEL_ERROR)
    mock_initialise_connection.assert_called_once_with(mock_rmt_pc_1["ip"], mock_rmt_pc_1["creds"])
    mock_remote_tentative_calls.assert_called_once_with(mock_rmt_pc_1)


@patch("server_mon.ErrorHandler", autospec=True)
@patch("paramiko_client.SSHClient", autospec=True)
@patch("paramiko_client.paramiko.AutoAddPolicy", autospec=True)
def test_initialise_connection(mock_autoaddpolicy, mock_ssh_client, mock_error_handler, mock_rmt_pc_1):
    interrogator = SSHInterrogator(mock_error_handler)
    con_err_str = interrogator.initialise_connection(mock_rmt_pc_1["ip"], mock_rmt_pc_1["creds"])
    assert con_err_str is None
    mock_ssh_object = mock_ssh_client.return_value
    mock_ssh_object.load_system_host_keys.assert_called_once_with()
    mock_ssh_object.set_missing_host_key_policy.assert_called_once_with(mock_autoaddpolicy.return_value)
    mock_ssh_object.connect.assert_called_once_with(
        mock_rmt_pc_1["ip"],
        **mock_rmt_pc_1["creds"][0])
    mock_ssh_client.assert_called_once_with()


@patch("server_mon.ErrorHandler", autospec=True)
@patch("paramiko_client.SSHClient", autospec=True)
@patch("paramiko_client.paramiko.AutoAddPolicy", autospec=True)
def test_initialise_connection_alt_auth_method(mock_autoaddpolicy, mock_ssh_client, mock_error_handler, mock_rmt_pc_2):
    interrogator = SSHInterrogator(mock_error_handler)
    mock_ssh_object = mock_ssh_client.return_value
    mock_ssh_object.connect.side_effect = [AuthenticationException, None]
    con_err_str = interrogator.initialise_connection(mock_rmt_pc_2["ip"], mock_rmt_pc_2["creds"])
    assert con_err_str is None
    mock_ssh_object.load_system_host_keys.assert_called_once_with()
    mock_ssh_object.set_missing_host_key_policy.assert_called_once_with(mock_autoaddpolicy.return_value)
    mock_ssh_object.connect.assert_has_calls([
        call(
            mock_rmt_pc_2["ip"],
            **mock_rmt_pc_2["creds"][0]
        ),
        call(
            mock_rmt_pc_2["ip"],
            **mock_rmt_pc_2["creds"][1]
        )
    ])
    mock_ssh_client.assert_called_once_with()


@patch("server_mon.ErrorHandler", autospec=True)
@patch("paramiko_client.SSHClient", autospec=True)
@patch("paramiko_client.paramiko.AutoAddPolicy", autospec=True)
def test_initialise_connection_auth_exception(
        mock_autoaddpolicy, mock_ssh_client, mock_error_handler, mock_rmt_pc_1):
    interrogator = SSHInterrogator(mock_error_handler)
    mock_ssh_object = mock_ssh_client.return_value
    mock_ssh_object.connect.side_effect = AuthenticationException
    con_err_str = interrogator.initialise_connection(
        mock_rmt_pc_1["ip"], mock_rmt_pc_1["creds"])
    assert con_err_str == f"No credentials were accepted by the remote host: " \
                          f"{mock_rmt_pc_1['ip']}"
    mock_ssh_object.load_system_host_keys.assert_called_once_with()
    mock_ssh_object.set_missing_host_key_policy.assert_called_once_with(
        mock_autoaddpolicy.return_value)
    mock_ssh_object.connect.assert_called_once_with(
        mock_rmt_pc_1["ip"],
        **mock_rmt_pc_1["creds"][0])
    mock_ssh_client.assert_called_once_with()


@patch("server_mon.ErrorHandler", autospec=True)
@patch("paramiko_client.SSHClient", autospec=True)
@patch("paramiko_client.paramiko.AutoAddPolicy", autospec=True)
def test_initialise_connection_bad_key_exception(
        mock_autoaddpolicy, mock_ssh_client, mock_error_handler, mock_rmt_pc_1):
    SAMPLE_PKEY1 = '''-----BEGIN PUBLIC KEY-----
    MFswDQYJKoZIhvcNAQEBBQADSgAwRwJAb/zKywAh+kmIT2i4imUxBtU9deJU2qyA
    MlbKqTcVHLqQBTnQ0LuPYsZSQMjLr/Ec/iLNrpyNdD+e2Apjnhk5PwIDAQAB
    -----END PUBLIC KEY-----'''

    SAMPLE_PKEY2 = '''-----BEGIN PUBLIC KEY-----
    MFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAICEJPZYhT1SIHEFJUiEMHNBdILWPTKh
    Csk0V5HzajjxFq+F8pAYtQE56Sr27ogVBB6K07yk/GPlcxEc95h9deECAwEAAQ==
    -----END PUBLIC KEY-----'''
    interrogator = SSHInterrogator(mock_error_handler)
    mock_ssh_object = mock_ssh_client.return_value
    mock_ssh_object.connect.side_effect = BadHostKeyException(
        mock_rmt_pc_1['ip'],
        Mock(PKey, get_base64=lambda: SAMPLE_PKEY1),
        Mock(PKey, get_base64=lambda: SAMPLE_PKEY2))
    con_err_str = interrogator.initialise_connection(
        mock_rmt_pc_1["ip"], mock_rmt_pc_1["creds"])
    assert f"'{mock_rmt_pc_1['ip']}' does not match" in con_err_str
    mock_ssh_object.load_system_host_keys.assert_called_once_with()
    mock_ssh_object.set_missing_host_key_policy.assert_called_once_with(
        mock_autoaddpolicy.return_value)
    mock_ssh_object.connect.assert_called_once_with(
        mock_rmt_pc_1["ip"],
        **mock_rmt_pc_1["creds"][0])
    mock_ssh_client.assert_called_once_with()


@patch("server_mon.ErrorHandler", autospec=True)
def test_query_free(mock_error_handler, free_lines_1):
    interrogator = mk_interrogator(mock_error_handler, free_lines_1)
    interrogator.query_free()
    assert interrogator.mem_avail == "3.2Gi"
    assert interrogator.swap_free == "4Gi"
    interrogator.client.exec_command.assert_called_once_with("free -h")
    mock_error_handler.append.assert_not_called()


@patch("server_mon.ErrorHandler", autospec=True)
def test_query_free_fail(mock_error_handler, free_lines_1):
    interrogator = mk_interrogator(mock_error_handler, free_lines_1, SENTINEL_ERROR)
    interrogator.query_free()
    mock_error_handler.append.assert_called_once_with(SENTINEL_ERROR)


@patch("server_mon.ErrorHandler", autospec=True)
def test_query_ssh_peers(mock_error_handler, sport22_lines):
    interrogator = mk_interrogator(mock_error_handler, sport22_lines)
    interrogator.query_ssh_peers(set())
    assert interrogator.ssh_peers == "61.177.173.18"
    interrogator.client.exec_command.assert_called_once_with("ss -tn sport = 22")
    mock_error_handler.append.assert_not_called()


@patch("server_mon.ErrorHandler", autospec=True)
def test_query_ssh_peers_fail(mock_error_handler, sport22_lines):
    interrogator = mk_interrogator(mock_error_handler, sport22_lines, SENTINEL_ERROR)
    interrogator.query_ssh_peers(set())
    mock_error_handler.append.assert_called_once_with(SENTINEL_ERROR)


@patch("server_mon.ErrorHandler", autospec=True)
def test_query_boot_time(mock_error_handler):
    interrogator = mk_interrogator(mock_error_handler, ["         system boot  2021-10-01 08:55", ""])
    interrogator.query_boot_time()
    assert interrogator.last_boot == "Oct  1 2021"  # "2021-10-01 08:55"
    interrogator.client.exec_command.assert_called_once_with("who -b")
    mock_error_handler.append.assert_not_called()


@patch("server_mon.ErrorHandler", autospec=True)
def test_query_boot_time_fail(mock_error_handler):
    interrogator = mk_interrogator(mock_error_handler, ["         system boot  2021-10-01 08:55", ""], SENTINEL_ERROR)
    interrogator.query_boot_time()
    mock_error_handler.append.assert_called_once_with(SENTINEL_ERROR)


@patch("server_mon.ErrorHandler", autospec=True)
def test_query_disk_free(mock_error_handler):
    interrogator = mk_interrogator(mock_error_handler, ["Avail", "124G"])
    interrogator.query_disk_free()
    assert interrogator.disk_avail == "124G"
    interrogator.client.exec_command.assert_called_once_with("df -h --output=avail /")
    mock_error_handler.append.assert_not_called()


@patch("server_mon.ErrorHandler", autospec=True)
def test_query_disk_free_fail(mock_error_handler):
    interrogator = mk_interrogator(mock_error_handler, ["Avail", "124G"], SENTINEL_ERROR)
    interrogator.query_disk_free()
    mock_error_handler.append.assert_called_once_with(SENTINEL_ERROR)


def test_remote_tentative_calls():
    fake_instance = Mock(SSHInterrogator)
    mock_rmt_pc = {
        "ssh_peers": "NOO.YOO.GET.LOS",
        "known_ports": "100,220,441",
    }
    fake_instance.parse_user_csv.side_effect = SSHInterrogator.parse_user_csv
    SSHInterrogator.remote_tentative_calls(fake_instance, mock_rmt_pc)
    fake_instance.query_free.assert_called_once_with()
    fake_instance.query_boot_time.assert_called_once_with()
    fake_instance.query_disk_free.assert_called_once_with()
    fake_instance.parse_user_csv.assert_has_calls([
        call(mock_rmt_pc.get("ssh_peers", "")),
        call(mock_rmt_pc.get("known_ports", "")),
    ])
    fake_instance.query_ssh_peers.assert_called_once_with(
        {generalised_functions.PUBLIC_IP, "NOO.YOO.GET.LOS"})
    fake_instance.query_ports.assert_called_once_with(
        SSHInterrogator.parse_user_csv(mock_rmt_pc["known_ports"]))


def test_read_gpu():
    gpu = MinerInterrogator.read_gpu(
        '|   0  GeForce GTX 166...  Off  | 00000000:01:00.0  On |                  N/A |\n')
    assert gpu == 0
    gpu = MinerInterrogator.read_gpu(
        '|   1  GeForce GTX 166...  Off  | 00000000:02:00.0  On |                  N/A |\n')
    assert gpu == 1
    gpu = MinerInterrogator.read_gpu(
        '| 38%   42C    P2    77W /  78W |   4835MiB /  5944MiB |    100%      Default |\n')
    assert gpu is None


@patch("server_mon.ErrorHandler", autospec=True)
@patch("paramiko_client.MinerInterrogator.read_gpu", autospec=True, side_effect=[0, 1, 2, None])
def test_query_gpus(mock_read_gpu, mock_error_handler, nvidia_smi_lines_1):
    interrogator = MinerInterrogator(mock_error_handler)
    patch_interrogator_client(interrogator, nvidia_smi_lines_1)
    interrogator.query_gpus()
    assert interrogator.g_pwr == ['77', '114', '86']
    assert interrogator.g_mem == ['4835', '4806', '4790']
    assert interrogator.g_tmp == ['42', '58', '66']
    mock_read_gpu.assert_has_calls(
        [call('|   0  GeForce GTX 166...  Off  | 00000000:01:00.0  On |                  N/A |\n'),
         call('|   1  GeForce RTX 2060    Off  | 00000000:02:00.0 Off |                  N/A |\n'),
         call('|   2  GeForce GTX 3060    Off  | 00000000:03:00.0 Off |                  N/A |\n'),
         call('                                                                               \n')])


@patch("server_mon.ErrorHandler", autospec=True)
@patch("paramiko_client.SSHInterrogator.initialise_connection", return_value=None)
@patch("paramiko_client.MinerInterrogator.query_gpus")
@patch("paramiko_client.SSHInterrogator.remote_tentative_calls")
def test_miner_do_queries(
        mock_remote_tentative_calls, mock_query_gpus,
        mock_initialise_connection, mock_error_handler,
        mock_rmt_pc_1):
    interrogator = MinerInterrogator(mock_error_handler)
    interrogator.do_queries(mock_rmt_pc_1)
    mock_initialise_connection.assert_called_once_with(mock_rmt_pc_1["ip"], mock_rmt_pc_1["creds"])
    mock_query_gpus.assert_called_once_with()
    mock_remote_tentative_calls.assert_called_once_with(mock_rmt_pc_1)
    mock_error_handler.append.assert_not_called()


@patch("server_mon.ErrorHandler", autospec=True)
@patch("paramiko_client.SSHInterrogator.initialise_connection", side_effect=SENTINEL_ERROR)
def test_miner_do_queries_fail(mock_initialise_connection, mock_error_handler, mock_rmt_pc_1):
    interrogator = MinerInterrogator(mock_error_handler)
    interrogator.do_queries(mock_rmt_pc_1)
    mock_initialise_connection.assert_called_once_with(
        mock_rmt_pc_1["ip"], mock_rmt_pc_1["creds"])
    mock_error_handler.append.assert_called_once_with(SENTINEL_ERROR)


