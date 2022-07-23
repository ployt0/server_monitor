import argparse
import datetime
import smtplib
from email.message import EmailMessage
from typing import List
from unittest.mock import Mock, patch, call, sentinel, mock_open

import pytest

from generalised_functions import find_cells_under, format_ipv4, plural, \
    send_email, \
    compose_email, parse_args_for_monitoring, ChecksInterface, \
    email_wout_further_checks, load_results, RESULTS_DIR, \
    ErrorHandler, _MONITOR_EMAIL, ResultHolder, DATE_MON_FMT, process_args, \
    IInterrogator, iterate_rmt_servers, convert_python_date_to_human


def test_easy_find_cells_under(ss_lines_1):
    # Here we have cells both inside and outside of the column headers.
    cells = find_cells_under(ss_lines_1, "Local Address:Port")
    assert cells == ["42.8.101.220:22", "42.8.101.220:22", "42.8.101.220:22"]
    cells = find_cells_under(ss_lines_1, "Peer Address:Port")
    assert cells == ["121.44.111.12:45900", "61.177.173.18:51931", "222.186.30.112:61668"]


def test_harder_find_cells_under(ss_lines_2):
    # Here we have the more extreme case where the columns are cramped (as far as they go without wrapping).
    # This causes problems because taking a delimiter of 1 space splits some column headers.
    # I would like to unlimit the pty width in paramiko.
    cells = find_cells_under(ss_lines_2, "Local Address:Port")
    assert cells == ["42.8.101.220:22", "42.8.101.220:22", "42.8.101.220:22", "42.8.101.220:22"]
    cells = find_cells_under(ss_lines_2, "Peer Address:Port")
    assert cells == ["121.44.111.12:45900", "61.177.173.18:29922", "61.177.173.18:55557", "61.177.173.18:35779"]


def test_format_ipv4():
    # todo: a future version should move the node IP into the file name, so 1:1, node:file.
    assert format_ipv4("1.1.1.1") == "  1.  1.  1.  1"
    assert format_ipv4("  1.  1.  1.  1") == "  1.  1.  1.  1"
    assert format_ipv4("111.111.111.111") == "111.111.111.111"


def test_plural():
    assert plural(4) == "s"
    assert plural(1) == ""
    assert plural(4, "eses") == "eses"
    assert plural(1, "eses") == ""
    assert plural([4], "eses") == ""
    assert plural([1, 2, 34], "eses") == "eses"


@patch("generalised_functions.datetime", spec=datetime)
def test_convert_python_date_to_human(mock_datetime):
    mock_datetime.utcnow = Mock(
        return_value=datetime.datetime(2022, 1, 13, 13, 30, 00))
    mock_datetime.strptime = datetime.datetime.strptime
    assert convert_python_date_to_human("2022-07-06 21:31") == "Jul  6 21:31"
    assert convert_python_date_to_human("2021-07-06 21:31") == "Jul  6 2021"
    assert convert_python_date_to_human("2022-07-26 21:31") == "Jul 26 21:31"
    assert convert_python_date_to_human("2021-07-26 21:31") == "Jul 26 2021"


@patch("generalised_functions.smtplib.SMTP", spec=smtplib.SMTP)
def test_send_email(patched_smtp):
    msg = EmailMessage()
    badaddy = "superbadaddy"
    badpass = "guessed"
    send_email(msg, badaddy, badpass)
    assert msg["From"] == badaddy
    patched_smtp.assert_called_once_with("smtp." + badaddy, 587)
    mock_smtp = patched_smtp.return_value
    mock_smtp.ehlo.assert_has_calls([call(), call()])
    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once_with(badaddy, badpass)
    mock_smtp.send_message.assert_called_once()


@patch("generalised_functions.EmailMessage.set_content",
       spec=EmailMessage.set_content)
@patch("generalised_functions.plural", return_value="eze")
@patch("generalised_functions.tabulate_csv_as_html",
       return_value="sentinel.content")
def test_compose_email_unique_ips(patched_tabulate_csv_as_html, patched_plural,
                                  patched_email_set_content):
    results = ["sentinel.result1", "sentinel.result2", "sentinel.result3"]
    check_results = [Mock(ChecksInterface, to_csv=(lambda y: lambda: y)(x)) for
                     x in results]
    msg = compose_email(check_results, "dear@sir.com", "ipv4", "ewok", "")
    assert msg["To"] == "dear@sir.com"
    assert msg["Subject"] == "3 ewok statuseze"
    patched_email_set_content.assert_called_once_with(
        "sentinel.content\n<hr/>\nsentinel.content\n<hr/>\nsentinel.content",
        subtype='html')
    patched_plural.assert_called_once_with(check_results, "es")
    patched_tabulate_csv_as_html.assert_has_calls([
        call("ipv4", [check_results[0]]),
        call("ipv4", [check_results[1]]),
        call("ipv4", [check_results[2]])], any_order=False)


@patch("generalised_functions.EmailMessage.set_content",
       spec=EmailMessage.set_content)
@patch("generalised_functions.plural", return_value="eze")
@patch("generalised_functions.tabulate_csv_as_html",
       return_value="sentinel.content")
def test_compose_email(patched_tabulate_csv_as_html, patched_plural,
                       patched_email_set_content):
    check_results = [Mock(ChecksInterface, to_csv=(lambda y: lambda: y)(x))
                     for x in
                     [
                         "1,metric1.1",
                         "1,metric1.2",
                         "1,metric1.3",
                         "2,metric1.1"
                     ]]
    msg = compose_email(
        check_results, "dear@sir.com", "ipv4,metric1", "ewok", "")
    assert msg["To"] == "dear@sir.com"
    assert msg["Subject"] == "4 ewok statuseze"
    patched_email_set_content.assert_called_once_with(
        "sentinel.content\n<hr/>\nsentinel.content", subtype='html')
    patched_plural.assert_called_once_with(check_results, "es")
    patched_tabulate_csv_as_html.assert_has_calls([
        call("ipv4,metric1",
             [check_results[0], check_results[1], check_results[2]]),
        call("ipv4,metric1", [check_results[3]])])


def test_parse_args_for_monitoring_help():
    with pytest.raises(SystemExit):
        parse_args_for_monitoring(["-h"], "sentinel.monitored")


MOCK_ARGS_LIST = ["sentinel.email_addy", "sentinel.email_password"]
MOCK_UNIT_NAME = "sentinel.monitored"


EXPECTED_MOCK_ARGS_OUT = dict(
    email_addy="sentinel.email_addy",
    email_to=None,
    nodes_file="monitored_sentinel.monitoreds.json",
    password="sentinel.email_password",
    send_on_success=False
)


def test_parse_args_for_monitoring_typical_use():
    args = parse_args_for_monitoring(MOCK_ARGS_LIST, MOCK_UNIT_NAME)
    assert args == argparse.Namespace(**EXPECTED_MOCK_ARGS_OUT)


def test_parse_args_for_monitoring_to_get_emailed():
    args = parse_args_for_monitoring(MOCK_ARGS_LIST + ["-esentinel.recipient_email_addy"], MOCK_UNIT_NAME)
    assert args == argparse.Namespace(**{**EXPECTED_MOCK_ARGS_OUT, **{"email_to": "sentinel.recipient_email_addy"}})


def test_parse_args_for_monitoring_custom_nodes_file():
    args = parse_args_for_monitoring(MOCK_ARGS_LIST + ["-nsentinel.nodes_file"], MOCK_UNIT_NAME)
    assert args == argparse.Namespace(**{**EXPECTED_MOCK_ARGS_OUT, **{"nodes_file": "sentinel.nodes_file"}})


@patch("generalised_functions.datetime", spec=datetime)
@patch("generalised_functions.load_results", return_value=sentinel.results)
@patch("generalised_functions.compose_email", return_value=sentinel.msg)
@patch("generalised_functions.send_email")
def test_email_wout_further_checks(mock_send_email, mock_compose_email, mock_load_results, mock_datetime):
    mock_datetime.utcnow = Mock(return_value=datetime.datetime(2000, 1, 13, 13, 30, 00))
    email_month_to = "feedmenow@datahog"
    mock_check_result = Mock(ChecksInterface)
    email_wout_further_checks(email_month_to, sentinel.sender, sentinel.password, mock_check_result)
    mock_send_email.assert_called_once_with(sentinel.msg, sentinel.sender, sentinel.password)
    mock_load_results.assert_called_once_with(
        "0001", mock_check_result.result_from_csv, mock_check_result.get_unit_name())
    mock_compose_email.assert_called_once_with(
        sentinel.results, "feedmenow@datahog", mock_check_result.get_header(),
        mock_check_result.get_unit_name(), " for 0001")


def test_load_results():
    with patch("builtins.open", mock_open(read_data="ta\nyay\naye\nnay\n")) as mocked_open:
        yymm = "4499"
        results = load_results(yymm, lambda x: x, sentinel.unit)
        print(results)
        mocked_open.assert_called_once_with("{}/{}_{}.csv".format(RESULTS_DIR, sentinel.unit, yymm), "r")
        assert results == ["ta\n", "yay\n", "aye\n", "nay\n"]


def test_error_handler():
    error_handler = ErrorHandler()
    assert error_handler.msg["To"] == _MONITOR_EMAIL


def test_error_handler_append():
    prerolled_err = RuntimeError("testing")
    error_handler = get_minimal_error_handler([prerolled_err])
    assert error_handler.first_error == prerolled_err
    assert error_handler.errors["here"] == [prerolled_err]


def get_minimal_error_handler(errors_to_add: List[Exception]):
    """Convenience method for getting an error handler which contains something to write about."""
    error_handler = ErrorHandler()
    error_handler.current_ip = "here"
    for err in errors_to_add:
        error_handler.append(err)
    return error_handler


def test_error_handler_set_subject_no_errors():
    error_handler = ErrorHandler()
    error_handler.set_subject(sentinel.unit_name)
    assert error_handler.msg["Subject"] == "0 errors on 0 (failing) sentinel.unit_names, first at None: None"


def test_error_handler_set_subject_1_error():
    error_handler = ErrorHandler()
    error_handler.current_ip = "here"
    prerolled_err = RuntimeError("testing")
    error_handler.append(prerolled_err)
    error_handler.set_subject(sentinel.unit_name)
    assert error_handler.msg["Subject"] == "1 error on 1 (failing) sentinel.unit_name, first at here: testing"


@patch("generalised_functions.send_email")
def test_error_handler_email_traces(mock_send_email):
    prerolled_err = RuntimeError("testing")
    error_handler = get_minimal_error_handler([prerolled_err])
    addy, password = "bob@blueyonder", "password"
    error_handler.email_traces(addy, password, sentinel.unit_name)
    mock_send_email.assert_called_once_with(error_handler.msg, addy, password)
    # No traceback, managing line numbers would be tricky:
    assert error_handler.msg.get_payload() ==\
           "================\nhere\nRuntimeError: testing\n\n\n================\n\n"


def test_result_holder():
    t1 = datetime.datetime.utcnow()
    result_holder = ResultHolder()
    t2 = datetime.datetime.utcnow()
    assert t1 <= result_holder.time <= t2


def test_result_holder_appends():
    result_holder = ResultHolder()
    check_result = Mock(ChecksInterface)
    result_holder.append(check_result)
    assert result_holder.results == [check_result]


def test_result_holder_saves():
    result_holder = ResultHolder()
    greet_sequence = ["hi", "hello", "good day", "evening"]
    # A second lambda wraps the original to capture the loop iterator which is lazily evaluated (captured when used).
    check_results = [Mock(ChecksInterface, to_csv=(lambda y: lambda: y)(x)) for x in greet_sequence]
    for result in check_results:
        result_holder.append(result)
    with patch("builtins.open", mock_open()) as mocked_open:
        result_holder.save(sentinel.unit_name)
        mocked_open.assert_called_once_with(
            "{}/sentinel.unit_name_{}.csv".format(RESULTS_DIR, result_holder.time.strftime(DATE_MON_FMT)), "a+")
        mocked_open.return_value.write.assert_has_calls([call(x) for x in greet_sequence])


@patch("generalised_functions.parse_args_for_monitoring", return_value=type('', (), {
    "email_to": None,
    "email_addy": sentinel.email_addy,
    "password": sentinel.password,
    "nodes_file": sentinel.nodes_file,
    "send_on_success": False
})())
@patch("generalised_functions.ChecksInterface")
@patch("generalised_functions.IInterrogator", autospec=True)
@patch("generalised_functions.ErrorHandler", autospec=True)
@patch("generalised_functions.ResultHolder", autospec=True)
@patch("generalised_functions.iterate_rmt_servers")
def test_process_args(
        mock_iterate_rmt_servers, mock_result_holder, mock_err_handler, mock_interrog, mock_ci, mock_parse_args):
    mock_ci.get_unit_name.return_value = sentinel.unit
    mock_err_handler.return_value.errors = {}
    process_args(sentinel.args_list, mock_ci, mock_interrog)
    mock_parse_args.assert_called_once_with(sentinel.args_list, sentinel.unit)
    mock_result_holder.assert_called_once_with()
    mock_iterate_rmt_servers.assert_called_once_with(
        sentinel.nodes_file,
        mock_ci,
        mock_interrog,
        mock_result_holder.return_value)


@patch("generalised_functions.parse_args_for_monitoring", return_value=type('', (), {
    "email_to": None,
    "email_addy": sentinel.email_addy,
    "password": sentinel.password,
    "nodes_file": sentinel.nodes_file,
    "send_on_success": True
})())
@patch("generalised_functions.send_email")
@patch("generalised_functions.compose_email", return_value=sentinel.msg)
@patch("generalised_functions.ChecksInterface")
@patch("generalised_functions.IInterrogator", autospec=True)
@patch("generalised_functions.ErrorHandler", autospec=True)
@patch("generalised_functions.ResultHolder", autospec=True)
@patch("generalised_functions.iterate_rmt_servers")
def test_process_args_then_send(
        mock_iterate_rmt_servers, mock_result_holder, mock_err_handler, mock_interrog,
        mock_ci, mock_compose_email, mock_send_email, mock_parse_args):
    mock_ci.get_unit_name.return_value = sentinel.unit
    mock_ci.get_header.return_value = sentinel.header
    mock_result_holder.return_value.results = sentinel.results
    mock_err_handler.return_value.errors = {}
    process_args(sentinel.args_list, mock_ci, mock_interrog)
    mock_parse_args.assert_called_once_with(sentinel.args_list, sentinel.unit)
    mock_result_holder.assert_called_once_with()
    mock_iterate_rmt_servers.assert_called_once_with(
        sentinel.nodes_file,
        mock_ci,
        mock_interrog,
        mock_result_holder.return_value)
    mock_compose_email.assert_called_once_with(
        sentinel.results, _MONITOR_EMAIL, sentinel.header, sentinel.unit, "")
    mock_send_email.assert_called_once_with(sentinel.msg, sentinel.email_addy, sentinel.password)


@patch("generalised_functions.parse_args_for_monitoring", return_value=type('', (), {
    "email_to": sentinel.email_to,
    "email_addy": sentinel.email_addy,
    "password": sentinel.password,
    "nodes_file": sentinel.nodes_file,
    "send_on_success": False
})())
@patch("generalised_functions.ChecksInterface")
@patch("generalised_functions.email_wout_further_checks", autospec=True)
@patch("generalised_functions.IInterrogator", autospec=True)
@patch("generalised_functions.ErrorHandler", autospec=True)
@patch("generalised_functions.ResultHolder", autospec=True)
@patch("generalised_functions.iterate_rmt_servers")
def test_process_args_and_email(mock_iterate_rmt_servers, mock_result_holder, mock_err_handler, mock_interrog,
                                mock_email_wout_further_checks, mock_ci, mock_parse_args):
    mock_ci.get_unit_name.return_value = sentinel.unit
    process_args(sentinel.args_list, mock_ci, Mock(IInterrogator))
    mock_parse_args.assert_called_once_with(sentinel.args_list, sentinel.unit)
    mock_result_holder.assert_not_called()
    mock_iterate_rmt_servers.assert_not_called()
    mock_err_handler.assert_not_called()
    mock_interrog.assert_not_called()
    mock_email_wout_further_checks.assert_called_with(
        sentinel.email_to, sentinel.email_addy, sentinel.password, mock_ci)


@patch("generalised_functions.IInterrogator", autospec=True)
@patch("generalised_functions.ResultHolder", autospec=True)
@patch("generalised_functions.ChecksInterface")
@patch("builtins.open", autospec=True)
@patch("generalised_functions.get_ping_latencies", autospec=True)
@patch("generalised_functions.json.load", autospec=True)
def test_iterate_rmt_servers_good_pings(
        mock_json_load, mock_get_pings, mocked_open, mock_ci,
        mock_result_holder, mock_interrog):
    iterable_latencies = ["21.43", "24.21", "27.87"]
    mock_get_pings.return_value = iterable_latencies
    mock_rmt_pc = {
        "servers": [{
            "ip": sentinel.ip
        }],
        "this_ip": sentinel.source_ip,
        "email_dest": "stringified_sentinel.monitoring_email"
    }
    mock_json_load.return_value = mock_rmt_pc
    err_handler = iterate_rmt_servers(
        sentinel.file_name, mock_ci, mock_interrog, mock_result_holder)
    assert err_handler.msg["To"] == mock_rmt_pc["email_dest"]
    mock_interrog.assert_called_once_with(
        err_handler, mock_rmt_pc["servers"][0],
        mock_result_holder, sentinel.ip, iterable_latencies)
    mock_get_pings.assert_called_once_with(err_handler, sentinel.ip)
    mocked_open.assert_called_once_with(sentinel.file_name, encoding="utf8")
