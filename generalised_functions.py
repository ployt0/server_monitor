from __future__ import annotations

import argparse
import requests
from datetime import datetime
import json
import smtplib
import traceback
from email.message import EmailMessage
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable, Union

from checks_interface import ChecksInterface
from html_tabulating import tabulate_csv_as_html
from ping_functions import get_ping_latencies


_MONITOR_EMAIL = "insert_email_here.Can_be_read_from_json_config."
PUBLIC_IP = "where we test from. Can be read from json config."
RESULTS_DIR = "results"
DATE_MON_FMT = "%y%m"
DAY_TIME_FMT = "%d %H:%M:%S"


def format_ipv4(ipv4: str):
    """Aligns the octets on the trailing dot."""
    return ".".join(["{:>3}".format(x) for x in ipv4.split(".")])


def send_email(msg: EmailMessage, email_from_addy: str, password: str):
    """
    EmailMessage will already contain particular fields, such as "subject".
    This function just uses an account to actually send it.

    To help keep your account secure, from **May 30, 2022**, Google no longer
    supports the use of third-party apps or devices which ask you to sign in
    to your Google Account using only your username and password.

    Solution:
        - Enable MFA
        - Crete "App password" per app (this app)
        - Use that password in place of your general password, I guess this
            provides accountability as to who (or what password) logged in
            as you.
    """
    # Use this account to send email to another:
    msg["From"] = email_from_addy
    # Attempt to make this work for other than gmail:
    smtp_server = "smtp." + email_from_addy.split("@")[-1]
    # 587 is the default TLS port we want to use:
    smtp = smtplib.SMTP(smtp_server, 587)
    try:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(msg["From"], password)
        smtp.send_message(msg)
    finally:
        smtp.quit()


def monitor_runners_ipv4():
    """Keep a record of what IP we're on which might be useful in
    whitelisting blocks for our future access to these servers."""
    runners_ip = get_public_ip()
    try:
        with open(f"{RESULTS_DIR}/public_ip_history.txt") as f:
            lines = f.read().splitlines()
            last_ip = lines[-1]
    except FileNotFoundError:
        last_ip = ""
    if last_ip != runners_ip:
        with open(f"{RESULTS_DIR}/public_ip_history.txt", "a+") as f:
            f.write(runners_ip)
    global PUBLIC_IP
    PUBLIC_IP = runners_ip


def plural(quantity, extension="s"):
    """
    :param quantity: list or integer.
    :param extension: how do extend to plural form.
    :return: plural extension if required.
    """
    if type(quantity) == list:
        count = len(quantity)
    elif type(quantity) == int:
        count = quantity
    else:
        raise ValueError(
            "Unexpected type {} of {}".format(type(quantity), quantity))
    return extension if count != 1 else ""


def convert_date_to_human_readable(date_str, date_formatter):
    """
    Standardises date string to show month, day, and time if year is same, else
    year.
    """
    py_date = datetime.strptime(date_str, date_formatter)
    if py_date.year == datetime.utcnow().year:
        fstring = "%b %-d %H:%M"
    else:
        fstring = "%b %-d %Y"
    return "{} {:>2} {}".format(*py_date.strftime(fstring).split(" "))


def find_cells_under(table_lines: List[str], col_header: str) -> List[str]:
    """
    Intended for ss lines. Assumes cell will be populated in each row
    (otherwise we overflow into next cell.)
    """
    col_indent = table_lines[0].find(col_header)
    cells = []
    for row in table_lines[1:]:
        cell_i = col_indent
        if row[cell_i] == " ":
            # advance to content:
            while row[cell_i] == " ":
                cell_i += 1
        else:
            # reverse to start of wider content:
            while row[cell_i] != " ":
                cell_i -= 1
            cell_i += 1  # jump to start of word
        cells.append(row[cell_i:].split()[0])
    return cells


class ErrorHandler:
    """
    Collects errors and indexes them as lists under the failing server's
    IP address.
    """
    def __init__(self):
        self.errors: Dict[str, List[Union[Exception, str]]] = {}
        self.msg = EmailMessage()
        self.msg["To"] = _MONITOR_EMAIL
        # Frame of reference for assigned stack traces:
        self.current_ip: Optional[str] = None
        self.first_error: Optional[Exception] = None
        self.first_ip: Optional[str] = None

    def append(self, error: Union[Exception, str]):
        if self.first_error is None:
            self.first_error = error
            self.first_ip = self.current_ip
        self.errors.setdefault(self.current_ip, []).append(error)

    def set_subject(self, unit_name: str):
        """
        This is not expected to be called when there are no errors to send.
        """
        subject = str(self.first_error)
        err_cnt = sum([len(x) for x in self.errors.values()])
        node_cnt = len(self.errors.keys())
        try:
            # Handle unknown errors:
            subject = "{} error{} on {} (failing) {}{}, first at {}: {}".format(
                err_cnt, plural(err_cnt), node_cnt, unit_name, plural(node_cnt),
                self.first_ip, self.first_error)
        except Exception as e:
            subject += "==Error setting subject, {}==".format(e)
        self.msg["Subject"] = subject

    def email_traces(self, email_addy: str, password: str, unit_name: str):
        """Sends all error information held."""
        self.set_subject(unit_name)
        message = ""
        for ip in self.errors.keys():
            message += "================\n{}\n".format(ip)
            for error in self.errors[ip]:
                if isinstance(error, Exception):
                    message += ''.join(traceback.format_exception(
                        type(error), value=error, tb=error.__traceback__))
                    message += '\n\n'
                else:
                    message += f"{error}\n\n"
            message += "================\n\n"
        self.msg.set_content(message)

        send_email(self.msg, email_addy, password)


class ResultHolder:
    """
    A class to hold check results in a list until they are ready for persisting.
    """

    def __init__(self):
        self.results: List[ChecksInterface] = []
        # Ideally all net operations should be done from a thread pool at once:
        self.time = datetime.utcnow()

    def append(self, result: ChecksInterface):
        self.results.append(result)

    def save(self, unit_name: str):
        Path(RESULTS_DIR).mkdir(parents=True, exist_ok=True)
        file_name = "{}/{}_{}.csv".format(
            RESULTS_DIR, unit_name, self.time.strftime(DATE_MON_FMT))
        with open(file_name, "a+") as f:
            for result in self.results:
                f.write(result.to_csv())


def compose_email(
        results: List, recipient: str, csv_header: str,
        server_description: str, description: str) -> EmailMessage:
    """
    Composes an email about node Check Statuses.

    :param results: list to put in email
    :param recipient: who to send to
    :param csv_header:
    :param server_description: adding this info to the subject, is the server
        a general node or specialist, like gpu?
    :param description: typically at/on/for time_str
    :return: EmailMessage
    """
    msg = EmailMessage()
    msg["To"] = recipient
    msg["Subject"] = "{} {} status{}{}".format(
        len(results), server_description, plural(results, "es"), description)
    ip_index = csv_header.split(",").index("ipv4")
    # unlike a simple set, this maintains order since python 3.7:
    distinct_ips = list(dict.fromkeys(
        row.to_csv().split(",")[ip_index] for row in results))
    results_by_ip = []
    for ip in distinct_ips:
        results_by_ip.append([row for row in results if row.to_csv().split(",")[ip_index] == ip])
    content = []
    for results_for_ip in results_by_ip:
        content.append(tabulate_csv_as_html(csv_header, results_for_ip))
    msg.set_content("\n<hr/>\n".join(content), subtype='html')
    return msg


def parse_args_for_monitoring(
        args_list: List[str], unit_name: str) -> argparse.Namespace:
    """
    CLI useful to monitoring scripts. The beauty is in what said scripts do
    with this info.

    :param args_list: command line arguments
    :param unit_name: so far we have "node" and "miner", describing what the
    role of the monitored.
    :return:
    """
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=unit_name.capitalize() + """ monitoring script.

Collects information on ping and http responses as well as some basic shell 
commands over SSH.

nodes_file is a list of servers with these fields:

{
  "servers": [
    {
      "ip": "21.151.211.10",
      "creds": [
        {
          "username": "megamind",
          "password": "fumbledpass",
          "key_filename": "/home/megs/.ssh/id_rsa"
        }
      ],
      "verify": "Path to public key or cert. True or False to enable/disable.",
      "home_page": "For node monitoring this is the origin or other URL to be requested.",
      "ssh_peers": "IPv4s of known, permitted ssh clients, separated by commas.",
      "known_ports": "known or permitted listening ports, separated by commas."
    }
  ],
  "this_ip": "ip address of testing machine, to exclude from peers list.",
  "email_dest": "email address to send notifications to."
}
""")
    parser.add_argument(
        "email_addy",
        help="Email (gmail) account to use for sending error and "
             "(optional) success emails.")
    parser.add_argument(
        "password",
        help="Password for the provided email (gmail) address.")
    parser.add_argument(
        "-e", "--email_to",
        help="Don't test, just email the month's log, to this address.")
    parser.add_argument(
        "-s", "--send_on_success",
        help="Send an email upon success.", action="store_true")
    parser.add_argument(
        "-n", "--nodes_file",
        help="Name of json file describing the nodes to monitor.",
        default="monitored_{}s.json".format(unit_name))
    args = parser.parse_args(args_list)
    return args


def load_results(
        yymm: str, line_reader: Callable[[str], Any], unit_name: str) -> List:
    """

    :param yymm: can define the file being loaded, though now this is further
        qualified according to the nature of tests and server.
    :param line_reader: callback for processing each line read from the loaded
        file.
    :param unit_name: Used to separate results according to unit, or node, name
        or type.
    :return:
    """
    file_name = "{}/{}_{}.csv".format(RESULTS_DIR, unit_name, yymm)
    results = []
    with open(file_name, "r") as f:
        lines = f.readlines()
        for line in lines:
            results.append(line_reader(line))
    return results


def email_wout_further_checks(
        email_to: str, sender_addy: str, sender_pw: str,
        check_result: ChecksInterface):
    yymm = datetime.utcnow().strftime(DATE_MON_FMT)
    results = load_results(
        yymm, check_result.result_from_csv, check_result.get_unit_name())
    msg = compose_email(
        results, email_to, check_result.get_header(),
        check_result.get_unit_name(), " for {}".format(yymm))
    send_email(msg, sender_addy, sender_pw)


IInterrogator = Callable[
    [ErrorHandler, dict, ResultHolder, str, List[str]], None]


def process_args(
        args_list: List[str],
        check_result: ChecksInterface,
        interrog_routine: IInterrogator):
    """
    Parses and processes command line arguments for monitoring scripts.

    :param args_list: command line args.
    :param check_result: a concrete dataclass of the abstract result holder.
    :param interrog_routine: called if ping responds and we want more results.
    :return:
    """
    args = parse_args_for_monitoring(args_list, check_result.get_unit_name())
    if args.email_to:
        email_wout_further_checks(
            args.email_to, args.email_addy, args.password, check_result)
        return
    result_holder = ResultHolder()
    err_handler = iterate_rmt_servers(args.nodes_file, check_result,
                        interrog_routine, result_holder)
    if err_handler.errors:
        err_handler.email_traces(args.email_addy, args.password,
                                 check_result.get_unit_name())
    result_holder.save(check_result.get_unit_name())
    if args.send_on_success:
        msg = compose_email(
            result_holder.results, _MONITOR_EMAIL, check_result.get_header(),
            check_result.get_unit_name(), "")
        send_email(msg, args.email_addy, args.password)


def iterate_rmt_servers(
        nodes_file_name: str, check_result: ChecksInterface,
        interrog_routine: IInterrogator, result_holder: ResultHolder)\
        -> ErrorHandler:
    """
    Opens the server list file and iterates through connecting to and querying
    all servers.

    :param nodes_file_name: source of json list of nodes.
    :param check_result: a concrete dataclass of the abstract result holder.
    :param err_handler: helps collect errors before acting, eg, to send an
        email, on them.
    :param interrog_routine: offers scope for the caller to perform more tests
        on a pingable machine.
    :param result_holder: acts like err_handler by collecting a quantity before
        performing an operation like emailing them.
    :return:
    """
    # Open nodes files from outside source control (don't commit credentials):
    with open(nodes_file_name, encoding="utf8") as f:
        config = json.load(f)
    global _MONITOR_EMAIL
    _MONITOR_EMAIL = config.get("email_dest", _MONITOR_EMAIL)
    err_handler = ErrorHandler()
    # PUBLIC_IP = config.get("this_ip", PUBLIC_IP)
    monitor_runners_ipv4()

    for rmt_pc in config["servers"]:
        ipv4 = rmt_pc["ip"]
        latencies = get_ping_latencies(err_handler, ipv4)
        if len(latencies) == 0:
            result_holder.append(
                check_result.from_fields(
                    [result_holder.time.strftime(DAY_TIME_FMT), ipv4]))
        else:
            interrog_routine(
                err_handler, rmt_pc, result_holder, ipv4, latencies)
    return err_handler


def get_public_ip() -> str:
    res = requests.get("http://ipinfo.io")
    jres = res.json()
    return jres["ip"]
