from unittest.mock import patch, sentinel, create_autospec

from server_mon import CheckResult, \
    process_args, \
    iterate_rmt_servers
from indie_gen_funcs import ErrorHandler, _MONITOR_EMAIL


@patch("server_mon.parse_args_for_monitoring", autospec=True, return_value=type('', (), {
    "email_to": None,
    "email_addy": sentinel.email_addy,
    "password": sentinel.password,
    "nodes_file": sentinel.nodes_file,
    "send_on_success": False
})())
@patch("server_mon.CheckResult", autospec=True)
@patch("server_mon.interrog_routine", autospec=True)
@patch("server_mon.ResultHolder", autospec=True)
@patch("server_mon.iterate_rmt_servers", autospec=True,
       return_value=create_autospec(ErrorHandler()))
def test_process_args(
        mock_iterate_rmt_servers, mock_result_holder,
        mock_interrog_routine, mock_c_res, mock_parse_args):
    process_args(sentinel.args_list, mock_c_res)
    mock_parse_args.assert_called_once_with(
        sentinel.args_list, mock_c_res.get_unit_name.return_value)
    mock_result_holder.assert_called_once_with()
    mock_iterate_rmt_servers.assert_called_once_with(
        sentinel.nodes_file,
        mock_c_res,
        mock_interrog_routine,
        mock_result_holder.return_value)


@patch("server_mon.parse_args_for_monitoring", autospec=True, return_value=type('', (), {
    "email_to": None,
    "email_addy": sentinel.email_addy,
    "password": sentinel.password,
    "nodes_file": sentinel.nodes_file,
    "send_on_success": True
})())
@patch("server_mon.send_email", autospec=True)
@patch("server_mon.compose_email", return_value=sentinel.msg)
@patch("server_mon.CheckResult", autospec=True)
@patch("server_mon.ResultHolder", autospec=True)
@patch("server_mon.interrog_routine", autospec=True)
@patch("server_mon.iterate_rmt_servers", autospec=True,
       return_value=create_autospec(ErrorHandler()))
def test_process_args_then_send(
        mock_iterate_rmt_servers, mock_interrog_routine,
        mock_result_holder, mock_c_res, mock_compose_email,
        mock_send_email, mock_parse_args):
    mock_c_res.get_unit_name.return_value = sentinel.unit
    mock_c_res.get_header.return_value = sentinel.header
    mock_result_holder.return_value.results = sentinel.results
    process_args(sentinel.args_list, mock_c_res)
    mock_parse_args.assert_called_once_with(sentinel.args_list, sentinel.unit)
    mock_result_holder.assert_called_once_with()
    mock_iterate_rmt_servers.assert_called_once_with(
        sentinel.nodes_file,
        mock_c_res,
        mock_interrog_routine,
        mock_result_holder.return_value)
    mock_compose_email.assert_called_once_with(
        sentinel.results, _MONITOR_EMAIL, sentinel.header, sentinel.unit, "")
    mock_send_email.assert_called_once_with(sentinel.msg, sentinel.email_addy, sentinel.password)


@patch("server_mon.parse_args_for_monitoring", autospec=True,
       return_value=type('', (), {
    "email_to": sentinel.email_to,
    "email_addy": sentinel.email_addy,
    "password": sentinel.password,
    "nodes_file": sentinel.nodes_file,
    "send_on_success": False
})())
@patch("server_mon.CheckResult", spec=CheckResult)
@patch("server_mon.email_wout_further_checks", autospec=True)
@patch("server_mon.ResultHolder", autospec=True)
@patch("server_mon.interrog_routine", autospec=True)
@patch("server_mon.iterate_rmt_servers", autospec=True,
       return_value=create_autospec(ErrorHandler()))
def test_process_args_and_email(
        mock_iterate_rmt_servers, mock_interrog_routine,
        mock_result_holder, mock_email_wout_further_checks,
        mock_c_res, mock_parse_args):
    mock_c_res.get_unit_name.return_value = sentinel.unit
    process_args(sentinel.args_list, mock_c_res)
    mock_parse_args.assert_called_once_with(sentinel.args_list, sentinel.unit)
    mock_result_holder.assert_not_called()
    mock_iterate_rmt_servers.assert_not_called()
    mock_interrog_routine.assert_not_called()
    mock_email_wout_further_checks.assert_called_once_with(
        sentinel.email_to, sentinel.email_addy, sentinel.password, mock_c_res)


@patch("server_mon.monitor_runners_ipv4", autospec=True)
@patch("server_mon.IInterrogator", autospec=True)
@patch("server_mon.ResultHolder", autospec=True)
@patch("server_mon.CheckResult", spec=CheckResult)
@patch("builtins.open", autospec=True)
@patch("server_mon.get_ping_latencies", autospec=True)
@patch("server_mon.json.load", autospec=True)
def test_iterate_rmt_servers_good_pings(
        mock_json_load, mock_get_pings, mocked_open, mock_c_res,
        mock_result_holder, mock_interrog, mock_ipv4_monitor):
    iterable_latencies = ["21.43", "24.21", "27.87"]
    mock_get_pings.return_value = iterable_latencies
    mock_rmt_pc = {
        "servers": [{
            "ip": sentinel.ip
        }],
        "email_dest": "stringified_sentinel.monitoring_email"
    }
    mock_json_load.return_value = mock_rmt_pc
    err_handler = iterate_rmt_servers(
        sentinel.file_name, mock_c_res, mock_interrog, mock_result_holder)
    assert err_handler.msg["To"] == mock_rmt_pc["email_dest"]
    mock_interrog.assert_called_once_with(
        err_handler, mock_rmt_pc["servers"][0],
        mock_result_holder, sentinel.ip, iterable_latencies)
    mock_get_pings.assert_called_once_with(err_handler, sentinel.ip)
    mocked_open.assert_called_once_with(sentinel.file_name, encoding="utf8")
    mock_ipv4_monitor.assert_called_once_with()


