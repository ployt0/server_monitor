from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional


def deserialise_simple_csv(line: str) -> List[Optional[str]]:
    """
    Assumes the second cell is a dot aligned IP address. In doing so it removes
    spaces from it.

    Also translates "None" to None in all cells.

    :param line: a string of csv fields.
    :return: split line.
    """
    cells: List = list(map(str.strip, line.split(",")))
    # Remove the dot alignment between octets:
    cells[1] = cells[1].replace(" ", "")
    # Deserialize None
    for i in range(len(cells)):
        if cells[i] == "None":
            cells[i] = None
    return cells


@dataclass(frozen=True)
class CheckResult:
    """
    `dataclass` was chosen because it can be frozen and immutable.

    A more readily extensible solution would be to keep these data fields in
    a dict, so that they may pick and choose attributes according to need,
    rather than attempting to implement ABC as interface. That would make
    from_csv tricky, since it operates without the header row. OTOH it would
    be immediately amenable to serialisation to/from json.
    """
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

    @classmethod
    def result_from_csv(cls, line: str) -> CheckResult:
        cells = deserialise_simple_csv(line)
        return cls(*cells)

    @classmethod
    def from_fields(cls, args: List[str]) -> CheckResult:
        return cls(*args)


def format_ipv4(ipv4: str):
    """Aligns the octets on the trailing dot."""
    return ".".join(["{:>3}".format(x) for x in ipv4.split(".")])