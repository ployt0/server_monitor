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
from typing import List

from generalised_functions import process_args, CheckResult


def main(args_list: List[str]):
    process_args(args_list, CheckResult)


if __name__ == "__main__":
    main(sys.argv[1:])
