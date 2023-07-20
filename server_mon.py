#!/usr/bin/env python3

"""
Server monitoring script.

Collects information on ping and http responses as well as some basic shell
commands over SSH. The order of these probes is important because it is not
unknown for a container to enter a deep sleep when not in use, heroku I'm
looking at you. We might not be able to SSH into these "things" but ping and
HTTP requests might best be observed without undue warning.
"""
from __future__ import annotations

import sys

import json
from typing import List, Callable

import indie_gen_funcs
from check_result import CheckResult
from indie_gen_funcs import ErrorHandler, ResultHolder, parse_args_for_monitoring, email_wout_further_checks, \
    compose_email, send_email, monitor_runners_ipv4, DAY_TIME_FMT
from interrog_routines import interrog_routine
from ping_functions import get_ping_latencies

IInterrogator = Callable[
    [ErrorHandler, dict, ResultHolder, str, List[str]], None]


def process_args(
        args_list: List[str],
        check_result: CheckResult):
    """
    Parses and processes command line arguments for monitoring scripts.

    :param args_list: command line args.
    :param check_result: a concrete dataclass of the abstract result holder.
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
            result_holder.results, indie_gen_funcs._MONITOR_EMAIL, check_result.get_header(),
            check_result.get_unit_name(), "")
        send_email(msg, args.email_addy, args.password)


def iterate_rmt_servers(
        nodes_file_name: str, check_result: CheckResult,
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
    indie_gen_funcs._MONITOR_EMAIL = config.get("email_dest", indie_gen_funcs._MONITOR_EMAIL)
    err_handler = ErrorHandler()
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


def main(args_list: List[str]):
    process_args(args_list, CheckResult)


if __name__ == "__main__":
    main(sys.argv[1:])
