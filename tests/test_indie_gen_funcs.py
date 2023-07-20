import argparse
import datetime
from email.message import EmailMessage
from typing import List
from unittest.mock import Mock, patch, call, sentinel, mock_open, create_autospec, MagicMock

import pytest

from check_result import format_ipv4
from indie_gen_funcs import send_email, monitor_runners_ipv4, \
    compose_email, parse_args_for_monitoring, CheckResult, \
    email_wout_further_checks, ResultHolder
from indie_gen_funcs import ErrorHandler, find_cells_under, \
    convert_date_to_human_readable, load_results, RESULTS_DIR, get_public_ip, plural
import indie_gen_funcs


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


@pytest.mark.parametrize("plural_args, expected_suffix", [
    ((4,), "s"),
    ((1,), ""),
    ((4, "eses",), "eses"),
    ((1, "eses",), ""),
    (([4], "eses",), ""),
    (([1, 2, 34], "eses",), "eses"),
])
def test_plural(plural_args, expected_suffix):
    assert plural(*plural_args) == expected_suffix


@pytest.mark.parametrize("who_b_date, expected_human_date", [
    ("Oct 30 06:10:57 2022", "Oct 30 06:10"),
    ("Oct 30 06:10:57 2021", "Oct 30 2021"),
    ("Oct 29 06:10:57 2022", "Oct 29 06:10"),
    ("Oct 29 06:10:57 2021", "Oct 29 2021")
])
@patch("indie_gen_funcs.datetime", autospec=True)
def test_convert_last_reboot_date_to_human(mock_datetime, who_b_date, expected_human_date):
    mock_datetime.utcnow = Mock(
        return_value=datetime.datetime(2022, 1, 13, 13, 30, 00))
    mock_datetime.strptime = datetime.datetime.strptime
    assert convert_date_to_human_readable(who_b_date, "%b %d %H:%M:%S %Y") == expected_human_date


@pytest.mark.parametrize("who_b_date, expected_human_date", [
    ("2022-07-06 21:31", "Jul  6 21:31"),
    ("2021-07-06 21:31", "Jul  6 2021"),
    ("2022-07-26 21:31", "Jul 26 21:31"),
    ("2021-07-26 21:31", "Jul 26 2021")
])
@patch("indie_gen_funcs.datetime", autospec=True)
def test_convert_who_b_date_to_human(mock_datetime, who_b_date, expected_human_date):
    mock_datetime.utcnow = Mock(
        return_value=datetime.datetime(2022, 1, 13, 13, 30, 00))
    mock_datetime.strptime = datetime.datetime.strptime
    assert convert_date_to_human_readable(who_b_date, "%Y-%m-%d %H:%M") == expected_human_date


@patch("indie_gen_funcs.smtplib.SMTP", autospec=True)
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


@patch.object(EmailMessage, "set_content", autospec=True)
@patch("indie_gen_funcs.plural", autospec=True, return_value="eze")
@patch("indie_gen_funcs.tabulate_csv_as_html", autospec=True,
       return_value="sentinel.content")
def test_compose_email_unique_ips(
        patched_tabulate_csv_as_html, patched_plural, patched_set_content):
    results = ["sentinel.result1", "sentinel.result2", "sentinel.result3"]
    check_results = [Mock(CheckResult, to_csv=(lambda y: lambda: y)(x)) for
                     x in results]
    msg = compose_email(check_results, "dear@sir.com", "ipv4", "ewok", "")
    assert msg["To"] == "dear@sir.com"
    assert msg["Subject"] == "3 ewok statuseze"
    patched_set_content.assert_called_once()
    # autospec=True causes the "self" object (msg) to capture here:
    patched_set_content.assert_called_once_with(
        msg, "sentinel.content\n<hr/>\nsentinel.content\n<hr/>\nsentinel.content", subtype="html")
    patched_plural.assert_called_once_with(check_results, "es")
    patched_tabulate_csv_as_html.assert_has_calls([
        call("ipv4", [check_results[0]]),
        call("ipv4", [check_results[1]]),
        call("ipv4", [check_results[2]])], any_order=False)


@patch("indie_gen_funcs.EmailMessage.set_content",
       spec=EmailMessage.set_content)
@patch("indie_gen_funcs.plural", return_value="eze")
@patch("indie_gen_funcs.tabulate_csv_as_html",
       return_value="sentinel.content")
def test_compose_email(patched_tabulate_csv_as_html, patched_plural,
                       patched_email_set_content):
    check_results = [Mock(CheckResult, to_csv=(lambda y: lambda: y)(x))
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


@pytest.mark.parametrize("extra_args, extra_expected_ns", [
    ([], {}),
    (["-esentinel.recipient_email_addy"], {"email_to": "sentinel.recipient_email_addy"}),
    (["-nsentinel.nodes_file"], {"nodes_file": "sentinel.nodes_file"}),
])
def test_parse_args_for_monitoring(extra_args, extra_expected_ns):
    MOCK_ARGS_LIST = ["sentinel.email_addy", "sentinel.email_password"]
    MOCK_UNIT_NAME = "sentinel.monitored"
    EXPECTED_MOCK_ARGS_OUT = dict(
        email_addy="sentinel.email_addy",
        email_to=None,
        nodes_file="monitored_sentinel.monitoreds.json",
        password="sentinel.email_password",
        send_on_success=False
    )
    args = parse_args_for_monitoring(MOCK_ARGS_LIST + extra_args, MOCK_UNIT_NAME)
    assert args == argparse.Namespace(**{**EXPECTED_MOCK_ARGS_OUT, **extra_expected_ns})


@patch("indie_gen_funcs.datetime", autospec=True)
@patch("indie_gen_funcs.load_results", autospec=True)
@patch("indie_gen_funcs.compose_email", autospec=True)
@patch("indie_gen_funcs.send_email", autospec=True)
def test_email_wout_further_checks(mock_send_email, mock_compose_email, mock_load_results, mock_datetime):
    mock_datetime.utcnow.return_value = datetime.datetime(2000, 1, 13, 13, 30, 00)
    email_month_to = "feedmenow@datahog"
    mock_check_result = Mock(CheckResult)
    email_wout_further_checks(email_month_to, sentinel.sender, sentinel.password, mock_check_result)
    mock_send_email.assert_called_once_with(
        mock_compose_email.return_value, sentinel.sender, sentinel.password)
    mock_load_results.assert_called_once_with(
        "0001", mock_check_result.result_from_csv, mock_check_result.get_unit_name())
    mock_compose_email.assert_called_once_with(
        mock_load_results.return_value, "feedmenow@datahog", mock_check_result.get_header(),
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
    assert error_handler.msg["To"] == indie_gen_funcs._MONITOR_EMAIL


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


@patch("indie_gen_funcs.send_email")
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
    check_result = Mock(CheckResult)
    result_holder.append(check_result)
    assert result_holder.results == [check_result]


def test_result_holder_saves():
    result_holder = ResultHolder()
    greet_sequence = ["hi", "hello", "good day", "evening"]
    # A second lambda wraps the original to capture the loop iterator which is lazily evaluated (captured when used).
    check_results = [Mock(CheckResult, to_csv=(lambda y: lambda: y)(x)) for x in greet_sequence]
    for result in check_results:
        result_holder.append(result)
    with patch("builtins.open", mock_open()) as mocked_open:
        result_holder.save(sentinel.unit_name)
        mocked_open.assert_called_once_with(
            "{}/sentinel.unit_name_{}.csv".format(
                RESULTS_DIR, result_holder.time.strftime(
                    indie_gen_funcs.DATE_MON_FMT)), "a+")
        mocked_open.return_value.write.assert_has_calls([call(x) for x in greet_sequence])


@patch("indie_gen_funcs.get_public_ip", autospec=True,
       return_value="sentinel.pub_ip")
def test_monitor_runners_changed_ipv4(mocked_get_public_ip):
    with patch("builtins.open",
               mock_open(read_data="8.8.8.8\n")) as mocked_open:
        monitor_runners_ipv4()
        mocked_open.assert_has_calls([
            call(f"{RESULTS_DIR}/public_ip_history.txt"),
            call(f"{RESULTS_DIR}/public_ip_history.txt", "a+")
        ], any_order=True)
        mocked_open.return_value.write.assert_called_once_with("sentinel.pub_ip\n")
    mocked_get_public_ip.assert_called_once_with()


@patch("indie_gen_funcs.get_public_ip", autospec=True,
       return_value="8.8.8.8")
def test_monitor_runners_unchanged_ipv4(mocked_get_public_ip):
    with patch("builtins.open",
               mock_open(read_data="8.8.8.8\n")) as mocked_open:
        monitor_runners_ipv4()
        mocked_open.assert_called_once_with(
            f"{RESULTS_DIR}/public_ip_history.txt")
        mocked_open.return_value.write.assert_not_called()
    mocked_get_public_ip.assert_called_once_with()


@patch("indie_gen_funcs.get_public_ip", autospec=True,
       return_value="sentinel.pub_ip")
def test_monitor_runners_first_ipv4(mocked_get_public_ip):
    open_mock = MagicMock()  # mock for open
    file_mock = MagicMock()  # mock for file returned from open
    open_mock.return_value.__enter__.side_effect = [
        FileNotFoundError, file_mock
    ]
    with patch("builtins.open", open_mock) as mocked_open:
        monitor_runners_ipv4()
        mocked_open.assert_has_calls([
            call(f"{RESULTS_DIR}/public_ip_history.txt"),
            call(f"{RESULTS_DIR}/public_ip_history.txt", "a+")
        ], any_order=True)
        file_mock.write.assert_called_once_with("sentinel.pub_ip\n")
    mocked_get_public_ip.assert_called_once_with()


@patch("indie_gen_funcs.requests.get", autospec=True)
def test_get_public_ip(mock_requests_get):
    test_ip = "8.8.8.8"
    mock_requests_get.return_value.json.return_value = {
        "ip": test_ip,
        "hostname": "9f271a71.btinternet.com",
        "city": "Birmingham",
        "loc": "52.4778,-1.8990",
        "org": "AS2856 British Telecommunications PLC",
        "postal": "B2",
        "readme": "https://ipinfo.io/missingauth"
    }
    pub_ip = get_public_ip()
    assert pub_ip == test_ip
