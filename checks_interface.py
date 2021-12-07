from __future__ import annotations
from abc import ABCMeta, abstractmethod
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


class ChecksInterface(metaclass=ABCMeta):
    """
    ABC as interface for the "checks" classes used for monitoring.

    The subclasses, which originally stood alone without inheritance, are
    dataclasses. `dataclass` was chosen because it can be frozen and immutable.

    A more readily extensible solution would be for them to keep these data
    fields in a dict, so that they may pick and choose attributes according to
    need, rather than attempting to implement ABC as interface. That would make
    from_csv tricky, since it operates without the header row. OTOH it would be
    immediately amenable to serialisation to/from json.
    """
    @staticmethod
    def get_header() -> str:
        pass

    @abstractmethod
    def to_csv(self) -> str:
        """Present class's fields as a csv row."""
        pass

    @classmethod
    def result_from_csv(cls, line: str) -> ChecksInterface:
        cells = deserialise_simple_csv(line)
        return cls(*cells)

    @classmethod
    def from_fields(cls, args: List[str]) -> ChecksInterface:
        return cls(*args)

    @classmethod
    @abstractmethod
    def get_unit_name(cls) -> str:
        """Name/role of the general type of server being monitored."""
        pass
