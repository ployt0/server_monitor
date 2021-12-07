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
from dataclasses import dataclass
from typing import Optional, List

import requests

from generalised_functions import format_ipv4, ErrorHandler, ResultHolder,\
    process_args, ChecksInterface, DAY_TIME_FMT
from paramiko_client import SSHInterrogator


@dataclass(frozen=True)
class CheckResult(ChecksInterface):
    local_time: str
    ipv4: str
    # rtt for round trip time, delta, or latency.
    ave_ping_rtt_ms: Optional[str] = None
    ping_max_ms: Optional[str] = None
    http_rtt_ms: Optional[str] = None
    http_code: Optional[str] = None
    mem_avail: Optional[str] = None
    swap_free: Optional[str] = None
    disk_avail: Optional[str] = None
    last_boot: Optional[str] = None
    ports: Optional[str] = None
    # Ensure this is last. It is most volatile, as attackers come (and go).
    ssh_peers: Optional[str] = None

    @staticmethod
    def get_header() -> str:
        return "{},{},{},{},{},{},{},{},{},{},{},{}\n".format(
            "time", "ipv4", "ping", "ping_max",
            "http_ms", "http_code", "mem_avail", "swap_free",
            "disk_avail", "last_boot", "ports", "ssh_peers")

    def to_csv(self) -> str:
        return "{},{},{},{},{},{},{},{},{},{},{},{}\n".format(
            self.local_time, format_ipv4(self.ipv4), self.ave_ping_rtt_ms,
            self.ping_max_ms, self.http_rtt_ms, self.http_code, self.mem_avail,
            self.swap_free, self.disk_avail, self.last_boot, self.ports,
            self.ssh_peers)

    @classmethod
    def get_unit_name(cls) -> str:
        return "node"


def interrog_routine(err_handler: ErrorHandler, rmt_pc: dict,
                     result_holder: ResultHolder,
                     ipv4: str, latencies: List[str]):
    ave_latency_ms = str(int(round(sum(map(float, latencies)) / len(latencies))))
    max_latency_ms = str(int(round(max(map(float, latencies)))))
    resp = requests.get(
        "http://{}{}".format(ipv4, rmt_pc.get("http_target", "")), timeout=5)
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
