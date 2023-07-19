#!/usr/bin/env python3

"""
A simplified (starting) version of server_mon.

Does no fancy SSH, or HTTP requests, just pings. Less to go wrong, less code,
fewer authentications. All it requires is you place your targets' (servers')
IP addresses on separate lines in a file called "ping_targets".

Node IP addresses are read from a text file with one on each line,
ping_targets.

Unlike server_mon, when this script is run from a systemd unit, it requires no
separate timer, it sleeps and repeats. I haven't tested this with systemd.
"""

from datetime import datetime
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple

from indie_gen_funcs import RESULTS_DIR
from check_result import format_ipv4
from ping_functions import ping

DATE_TIME_FMT = "%y%m%d %H:%M:%S"
DATE_FMT = "%y%m%d"


@dataclass(frozen=True)
class PingResult:
    local_time: str
    ipv4: str
    ave_latency_ms: Optional[int]
    max_latency_ms: Optional[int]


def main():
    with open("ping_targets", encoding="utf8") as f:
        inventory = f.readlines()

    Path(RESULTS_DIR).mkdir(parents=True, exist_ok=True)
    while True:
        ping_all_day(inventory)


def ping_all_day(inventory: List[str]) -> None:
    ping_list = []
    today = datetime.utcnow().strftime(DATE_FMT)
    while today == datetime.utcnow().strftime(DATE_FMT):
        start_time = time.time()
        # Place max window on this ping cycle of 30-90 minutes:
        resume_time = start_time + (30 + random.random() * 60) * 60
        for ipv4 in inventory:
            local_time = datetime.utcnow()
            ave_latency_ms, max_latency_ms = time_pings(ipv4)
            ping_list.append(PingResult(
                local_time.strftime(DATE_TIME_FMT), ipv4,
                ave_latency_ms, max_latency_ms))
        # Pinged everything, sleep before repeating:
        time.sleep(resume_time - time.time())
    save_days_pings(ping_list, today)


def save_days_pings(ping_list: List[PingResult], today: str) -> None:
    with open("{}/pings_{}.csv".format(RESULTS_DIR, today), "a+") as f:
        for ping_result in ping_list:
            f.write("{},{},{},{}\n".format(
                ping_result.local_time, format_ipv4(ping_result.ipv4),
                ping_result.ave_latency_ms, ping_result.max_latency_ms))


def time_pings(ipv4: str) -> Tuple[Optional[int], Optional[int]]:
    """Returns average follwed by max latency. Or double None."""
    result = ping(ipv4)
    output = result.stdout.decode()
    latencies = re.findall(r"time=([\d. ]+)ms", output)
    if result.returncode != 0 or len(latencies) == 0:
        ave_latency_ms = max_latency_ms = None
    else:
        ave_latency_ms = int(round(sum(map(float, latencies)) / len(latencies)))
        max_latency_ms = int(round(max(map(float, latencies))))
    return ave_latency_ms, max_latency_ms


if __name__ == "__main__":
    main()
