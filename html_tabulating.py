from __future__ import annotations

import re
from email.message import EmailMessage
from statistics import stdev, mean
from typing import List, Dict, Union, Tuple, Optional

from checks_interface import ChecksInterface


def find_invariant_cols(results: List[List[str]]) -> Dict[int, str]:
    """
    This is particularly helpful with a small number of highly similar servers.

    :param results: list(table) of lists(rows) of cells
    :return: map of invariant indices (of columns) to their value.
    """
    invariant_values = []
    invariant_indices = []
    # Pre-populate on first row
    for cell in results[0]:
        invariant_values.append(cell)
        invariant_indices.append(True)
    for row in results[1:]:
        for i, cell in enumerate(row):
            if invariant_values[i] != cell:
                invariant_indices[i] = False
    return {i: kv[1] for i, kv in enumerate(zip(invariant_indices, invariant_values)) if kv[0]}


Scalar = Union[float, int, None]
ScalarList = List[Scalar]


class RangeFinder:
    """
    This class expects numerical strings consisting of digits, underscores,
    units (Gi|G == 2^20), and the decimal place. Also the string literal
    "None" is understood.

    Underscores are used to separate related fields that don't warrant having
    separate columns.

    Negative values are not supported.
    """
    expression = re.compile(r'^([0-9]*\.?[0-9]+)(Ti|T|TB|Gi|G|GB|Mi|M|MB|Ki|K|KB)?$')
    powers = "KMGT"

    @staticmethod
    def get_scaled(mag: str, unit: Optional[str] = None) -> Scalar:
        """
        Maintain precision of the original string format.
        When presenting later we can round as desired.
        Whilst acknowledging Gi, I have no confidence that the OS will redefine
        GB or G in powers of 10.
        """
        mag = float(mag) if "." in mag else int(mag)
        if unit in ["T", "Ti", "TB"]:
            return mag * 2**40
        if unit in ["G", "Gi", "GB"]:
            return mag * 2**30
        if unit in ["M", "Mi", "MB"]:
            return mag * 2**20
        if unit in ["K", "Ki", "KB"]:
            return mag * 2**10
        return mag

    @staticmethod
    def is_considered_rangeable(cell_contents: str) -> bool:
        pieces = cell_contents.split("_")
        for piece in pieces:
            if piece == "None":
                continue
            if not RangeFinder.expression.match(piece):
                return False
        return True

    @staticmethod
    def to_numeric_list(cell_contents: str) -> List[Scalar]:
        pieces = cell_contents.split("_")
        numeric_list = []
        for piece in pieces:
            if piece == "None":
                numeric_list.append(None)
                continue
            if not RangeFinder.expression.match(piece):
                raise ValueError("Illegal non numeric: {}".format(piece))
            for unit_char in RangeFinder.powers:
                if unit_char in piece:
                    mag, unit = RangeFinder.split_mag_from_unit(piece, unit_char)
                    break
            else:
                mag = piece
                unit = None
            numeric_list.append(RangeFinder.get_scaled(mag, unit))
        return numeric_list

    @staticmethod
    def split_mag_from_unit(piece: str, unit_letter: str) -> Tuple[str, str]:
        mag = piece.split(unit_letter)[0]
        unit = unit_letter + piece.split(unit_letter)[1]
        return mag, unit

    @staticmethod
    def find_numeric_cols(results: List[List[str]]) -> Dict[int, List[List[Scalar]]]:
        """
        Finds numerical columns by looking for 0-1 periods and numbers.
        Finds underscore-delimited numerical columns.
        "None" is considered numerical for these purposes.
        Finds the ranges of these columns.

        :param results: list(table) of lists(rows) of cells
        :return: map of indices of numerical columns to their ranges.
        """
        numerical_ranges = {i: [] for i in range(len(results[0]))}
        for row in results:
            for i, cell in enumerate(row):
                # If rangeable:
                if i in numerical_ranges:
                    # Check still rangeable:
                    if not RangeFinder.is_considered_rangeable(cell):
                        del numerical_ranges[i]
                        continue
                    numerical_ranges[i].append(RangeFinder.to_numeric_list(cell))
        return numerical_ranges

    @staticmethod
    def unzip(column_values: List[List[Scalar]]) -> Tuple[List[Scalar]]:
        unzipped_object = zip(*column_values)
        return tuple(unzipped_object)

    @staticmethod
    def shrink_dps(value: str) -> str:
        """Use IEC sizing nomenclature and trim to under 3 significant figures."""
        unit_i = 0
        num_val = float(value)
        while num_val > 999:
            num_val /= 1024
            unit_i += 1
        if unit_i > 0:
            args = {
                "number": num_val
            }
            if num_val < 10:
                args["ndigits"] = 1
            new_num_str = str(round(**args))
            if new_num_str.endswith(".0"):
                new_num_str = new_num_str[:-2]
            return new_num_str + RangeFinder.powers[unit_i - 1] + "i"
        return value

    @staticmethod
    def summarise_numbers(column_values: List[Scalar]) -> Optional[Dict]:
        """Do stat analysis on the numbers then trim the irrelevant."""
        # Deal with edge cases where we have one or zero measurements.
        val_count = len([x for x in column_values if x is not None])
        if val_count == 0:
            return None
        if val_count == 1:
            stats = {
                "mean": str(
                    round([x for x in column_values if x is not None][0], 2)),
                "nulls": str(len([x for x in column_values if x is None])),
            }
            stats["mean"] = RangeFinder.shrink_dps(stats["mean"])
        else:
            stats = {
                "mean": str(round(mean([x for x in column_values if x is not None]), 2)),
                "stdev": str(round(stdev([x for x in column_values if x is not None]), 2)),
                "min": str(round(min([x for x in column_values if x is not None]), 2)),
                "max": str(round(max([x for x in column_values if x is not None]), 2)),
                "nulls": str(len([x for x in column_values if x is None])),
            }
            stats["min"] = RangeFinder.shrink_dps(stats["min"])
            stats["mean"] = RangeFinder.shrink_dps(stats["mean"])
            stats["max"] = RangeFinder.shrink_dps(stats["max"])
            stats["stdev"] = RangeFinder.shrink_dps(stats["stdev"])
        if stats["nulls"] == "0":
            del stats["nulls"]
        return stats


def tabulate_csv_as_html(csv_header: str, results: List[ChecksInterface],
                         row_splits: int = 1) -> str:
    """
    :param csv_header: for the table header
    :param results: to tabulate
    :param row_splits: 1 gets the whole row on each line, 2 splits in half,
        3 into thirds, etc
    :return: html content string
    """
    table = [row.to_csv().split(",") for row in results]
    invariant_cols = find_invariant_cols(table)
    numeric_cols = RangeFinder.find_numeric_cols(table)
    trimmed_table = [
        [cell for i, cell in enumerate(row) if i not in invariant_cols]
        for row in table
    ]
    selected_columns = [cell for i, cell in enumerate(csv_header.split(",")) if i not in invariant_cols]
    col_cnt = len(selected_columns)
    # Entertained splitting in half for a while, but tables can get long that way.
    # There are better alternatives to clean data.
    row_width = col_cnt // row_splits
    content = "<table>" + get_row(selected_columns, row_width, "th")
    for row in trimmed_table:
        content += get_row(row, row_width, "td")
    content += "\n</table>\n"
    content += display_constants(csv_header.split(","), invariant_cols)
    numeric_cols = {k: v for k, v in numeric_cols.items() if k not in invariant_cols.keys()}
    content += display_statistics(csv_header.split(","), numeric_cols)
    return content


def get_row(row: List[str], cells_per_row: int, cell_tag: str):
    """
    :param row: list of cell contents
    :param cells_per_row: how many cells per row
    :param cell_tag: tag name for the cell, td and th being the possibilities known.
    :return: html describing the row
    """
    html_row = "\n<tr>\n"
    for i, cell in enumerate(row):
        if i == cells_per_row:
            # sub-divide natural row width:
            html_row += "\n</tr>\n<tr>"
        html_row += "<{}>".format(cell_tag) + cell + "</{}>".format(cell_tag)
    return html_row + "\n</tr>"


def display_constants(header: List[str], invariant_cols: Dict[int, str]) -> str:
    if not invariant_cols:
        return ""
    content = "\n<h3>Constants:</h3>\n<ul>"
    for item in invariant_cols.items():
        content += "\n<li><em>{}<em>: {}</li>\n".format(header[item[0]], item[1])
    content += "</ul>\n"
    return content


def display_statistics(header: List[str], numeric_cols: Dict[int, List[List[Scalar]]]) -> str:
    if not numeric_cols:
        return ""
    content = "\n<h3>Statistics:</h3>\n<ul>"
    for item in numeric_cols.items():
        if len(item[1][0]) == 1:
            stats = RangeFinder.summarise_numbers([x[0] for x in item[1]])
            # content += "\n<li><em>{}</em>: <pre>{}</pre></li>\n".format(header[item[0]], json.dumps(stats, indent=2))
            content += "\n<li><em>{}:</em>\n<ul>\n".format(header[item[0]])
            for k, v in stats.items():
                content += "<li><em>{}:</em> {}</li>\n".format(k, v)
            content += "</ul></li>\n"
        else:
            cols = RangeFinder.unzip(item[1])
            content += "\n<li><em>{}:</em>\n<ul>\n".format(header[item[0]])
            for i, col in enumerate(cols):
                stats = RangeFinder.summarise_numbers(col)
                # content += "<li><em>{}:</em>: <pre>{}</pre>\n</li>\n".format(i, json.dumps(stats, indent=2))
                content += "<li><em>{}:</em>\n<ul>\n".format(i)
                for k, v in stats.items():
                    content += "<li><em>{}:</em> {}</li>\n".format(k, v)
                content += "</ul></li>\n"
            content += "</ul></li>\n"
    content += "</ul>\n"
    return content
