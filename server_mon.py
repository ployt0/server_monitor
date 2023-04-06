#!/usr/bin/env python3

"""
Server monitoring script.

Collects information on ping and http responses as well as some basic shell
commands over SSH. The order of these probes is important because it is not
unknown for a container to enter a deep sleep when not in use, heroku I'm
looking at you. We might not be able to SSH into these "things" but ping and
HTTP requests might best be observed without undue warning.
"""

import sys
from typing import Optional, List

import requests
from requests.exceptions import SSLError

from generalised_functions import ErrorHandler, ResultHolder,\
    process_args, CheckResult, DAY_TIME_FMT
from paramiko_client import SSHInterrogator


def interrog_routine(err_handler: ErrorHandler, rmt_pc: dict,
                     result_holder: ResultHolder,
                     ipv4: str, latencies: List[str]):
    ave_latency_ms = str(int(round(sum(map(float, latencies)) / len(latencies))))
    max_latency_ms = str(int(round(max(map(float, latencies)))))
    try:
        resp = requests.get(rmt_pc["home_page"], timeout=5, verify=rmt_pc.get("verify", True))
    except SSLError as ssl_e:
        err_handler.append(ssl_e)
        resp = requests.get(rmt_pc["home_page"], timeout=5, verify=False)
    except requests.exceptions.ConnectionError as awol_e:
        # We failed. Not merely on TLS but the whole HTTP(S) response.
        err_handler.append(awol_e)
        # That will send us a whole, overly long, stack trace, later.
        return
    response_ms = str(int(round(1000 * resp.elapsed.total_seconds()))) \
        if resp.ok else None
    ssh_interrogator = SSHInterrogator(err_handler)
    ssh_interrogator.do_queries(rmt_pc)
    result_holder.append(CheckResult(
        result_holder.time.strftime(DAY_TIME_FMT), ipv4, ave_latency_ms,
        max_latency_ms, response_ms, str(resp.status_code),
        ssh_interrogator.mem_avail, ssh_interrogator.swap_free,
        ssh_interrogator.disk_avail, ssh_interrogator.last_boot,
        ssh_interrogator.ports, ssh_interrogator.ssh_peers
    ))


def main(args_list: List[str]):
    process_args(args_list, CheckResult, interrog_routine)


if __name__ == "__main__":
    main(sys.argv[1:])
