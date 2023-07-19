from __future__ import annotations

import argparse
import os
import smtplib
import traceback
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Callable
from typing import Dict, List, Union, Optional

import requests

from check_result import CheckResult
from html_tabulating import tabulate_csv_as_html

_MONITOR_EMAIL = "insert_email_here.Can_be_read_from_json_config."
PUBLIC_IP = "where we test from. Can be read from json config."
RESULTS_DIR = "results"
DATE_MON_FMT = "%y%m"
DAY_TIME_FMT = "%d %H:%M:%S"


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


def get_public_ip() -> str:
    res = requests.get("http://ipinfo.io")
    jres = res.json()
    return jres["ip"]


def monitor_runners_ipv4():
    """Keep a record of what IP we're on which might be useful in
    whitelisting blocks for our future access to these servers."""
    runners_ip = get_public_ip()
    Path(RESULTS_DIR).mkdir(parents=True, exist_ok=True)
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
    if os.name == 'nt':
        fstring = fstring.replace("-", "#")
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


class ResultHolder:
    """
    A class to hold check results in a list until they are ready for persisting.
    """

    def __init__(self):
        self.results: List[CheckResult] = []
        # Ideally all net operations should be done from a thread pool at once:
        self.time = datetime.utcnow()

    def append(self, result: CheckResult):
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
      "verify": "Optional path to public key or cert. True (default) or False to enable/disable.",
      "home_page": "Used for HTTP(S) request, as health check / heartbeat. eg 'https://example.com'",
      "ssh_peers": "IPv4 addresses of known, permitted ssh clients, separated by commas.",
      "known_ports": "known, permitted listening ports, separated by commas."
    }
  ],
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
        check_result: CheckResult):
    yymm = datetime.utcnow().strftime(DATE_MON_FMT)
    results = load_results(
        yymm, check_result.result_from_csv, check_result.get_unit_name())
    msg = compose_email(
        results, email_to, check_result.get_header(),
        check_result.get_unit_name(), " for {}".format(yymm))
    send_email(msg, sender_addy, sender_pw)




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