from __future__ import annotations

import platform
import re
import subprocess
from typing import List


def ping(host: str) -> subprocess.CompletedProcess:
    pkt_cnt_flag = "-n" if platform.system().lower() == "windows" else "-c"
    command = ['ping', pkt_cnt_flag, '4', host]

    return subprocess.run(command, capture_output=True)


def get_ping_latencies(err_handler, ipv4: str) -> List[str]:
    err_handler.current_ip = ipv4
    result = ping(ipv4)
    if result.returncode == 0:
        # An unreachable host can still return 0.
        output = result.stdout.decode()
        return re.findall(r"time=([\d. ]+)ms", output)
    return []
