#!/usr/bin/env python3

"""
Miner monitoring script.

Collects information on ping and http responses as well as some basic shell
commands over SSH.
"""

import sys
from dataclasses import dataclass
from typing import Optional, List, Union

from generalised_functions import format_ipv4, ErrorHandler, ResultHolder, \
    ChecksInterface, DAY_TIME_FMT, process_args
from paramiko_client import MinerInterrogator


@dataclass(frozen=True)
class CheckResult(ChecksInterface):
    local_time: str
    ipv4: str
    # rtt for round trip time, delta, or latency.
    ave_ping_rtt_ms: Optional[str] = None
    ping_max_ms: Optional[str] = None
    mem_avail: Optional[str] = None
    disk_avail: Optional[str] = None
    last_boot: Optional[str] = None
    g_tmp: Optional[str] = None
    g_mem: Optional[str] = None
    g_pwr: Optional[str] = None
    # Ensure this is last. It is most volatile, as attackers come (and go).
    ssh_peers: Optional[str] = None

    @staticmethod
    def get_header() -> str:
        return "{},{},{},{},{},{},{},{},{},{},{}\n".format(
            "time", "ipv4", "ping", "ping_max",
            "mem_avail", "disk_avail", "last_boot",
            "g_tmp(°C)", "g_mem(MB)", "g_pwr", "ssh_peers")

    def to_csv(self) -> str:
        return "{},{},{},{},{},{},{},{},{},{},{}\n".format(
            self.local_time, format_ipv4(self.ipv4), self.ave_ping_rtt_ms, self.ping_max_ms,
            self.mem_avail, self.disk_avail, self.last_boot,
            self.g_tmp, self.g_mem, self.g_pwr, self.ssh_peers)

    @classmethod
    def get_unit_name(cls) -> str:
        return "miner"


def display_opt_int_list(opt_int_list: List[Union[str, None]]) -> Optional[str]:
    if all(x is None for x in opt_int_list):
        return None
    copied_list = []
    for item in opt_int_list:
        if item is None:
            copied_list.append("None")
        else:
            copied_list.append(item)
    return "_".join(copied_list)


def interrog_routine(
        err_handler: ErrorHandler, rmt_pc: dict, result_holder: ResultHolder,
        ipv4: str, latencies: List[str]):
    ave_latency_ms = str(int(round(sum(map(float, latencies)) / len(latencies))))
    max_latency_ms = str(int(round(max(map(float, latencies)))))
    ssh_interrogator = MinerInterrogator(err_handler)
    ssh_interrogator.do_queries(rmt_pc)
    result_holder.append(CheckResult(
        result_holder.time.strftime(DAY_TIME_FMT), ipv4, ave_latency_ms,
        max_latency_ms, ssh_interrogator.mem_avail, ssh_interrogator.disk_avail,
        ssh_interrogator.last_boot,
        display_opt_int_list(ssh_interrogator.g_tmp),
        display_opt_int_list(ssh_interrogator.g_mem),
        display_opt_int_list(ssh_interrogator.g_pwr),
        ssh_interrogator.ssh_peers
    ))


def main(args_list: List[str]):
    process_args(args_list, CheckResult, interrog_routine)


if __name__ == "__main__":
    main(sys.argv[1:])
