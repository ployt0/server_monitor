import re
from typing import Dict, Set, Tuple, List, Optional, Union

import paramiko
from paramiko import SSHClient
from paramiko.ssh_exception import AuthenticationException

from generalised_functions import ErrorHandler, PUBLIC_IP, find_cells_under, \
    convert_python_date_to_human


class SSHInterrogator:
    def __init__(self, err_handler: ErrorHandler):
        self.mem_avail = None
        self.swap_free = None
        self.disk_avail = None
        self.last_boot = None
        self.ssh_peers = None
        self.ports = None
        self.err_handler = err_handler

    def do_queries(self, rmt_pc: Dict[str, Union[List[dict], str]]):
        # With paramiko/SSH, expect the unexpected, then recover and report the error.
        try:
            self.initialise_connection(rmt_pc["ip"], rmt_pc["creds"])
            self.remote_tentative_calls(rmt_pc)
        except Exception as e:
            self.err_handler.append(e)

    def initialise_connection(self, ip_address: str, credentials: List[Dict[str,str]]) -> None:
        """
        All of this should be wrapped in a try catch for when paramiko/network throws a curve ball.

        :param ip_address: to SSH to.
        :param credentials: a list of identities defined by username and either path to a private key
            or password. These are the same as used by SSHClient.connect.
        """
        self.client = SSHClient()
        self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        for creds in credentials:
            try:
                self.client.connect(ip_address, **creds)
                break
            except AuthenticationException:
                pass
        else:
            raise AuthenticationException("No credentials were accepted by the remote host: {}".format(ip_address))

    def remote_tentative_calls(self, rmt_pc: Dict[str, Union[List[dict], str]]):
        """
        All of this should be wrapped in a try catch for when paramiko/network
        throws a googly.
        """
        self.query_free()
        self.query_boot_time()
        self.query_disk_free()
        ssh_peers = self.parse_user_csv(rmt_pc.get("ssh_peers", ""))
        ssh_peers.add(PUBLIC_IP)
        self.query_ssh_peers(ssh_peers)
        self.query_ports(self.parse_user_csv(rmt_pc.get("known_ports", "")))

    @staticmethod
    def parse_user_csv(user_csv: str) -> Set[str]:
        users_set = set(user_csv.split(","))
        return users_set

    def query_disk_free(self):
        try:
            stdin, stdout, stderr = self.client.exec_command("df -h --output=avail /")
            self.disk_avail = stdout.readlines()[-1].strip()
        except Exception as e:
            self.err_handler.append(e)

    def query_boot_time(self):
        try:
            stdin, stdout, stderr = self.client.exec_command("who -b")
            # The result is numeric when run locally, but on some servers
            # it will begin with the month as 3 letters, which by convention
            # I will use convert_python_date_to_human to standardise to.
            uptime_line = stdout.readlines()[0].strip()
            up_since = uptime_line[len("system boot"):].strip()
            if "0" <= up_since[0] <= "9":
                up_since = convert_python_date_to_human(up_since)
            self.last_boot = up_since
        except Exception as e:
            self.err_handler.append(e)

    def query_ports(self, known_ports: Set[str]) -> None:
        """
        :param known_ports: ports we accept being open.
        """
        try:
            stdin, stdout, stderr = self.client.exec_command("ss -tuln")
            ss_lines = stdout.readlines()
            local_add_port = find_cells_under(ss_lines, "Local Address:Port")
            # Checking the local address may provide more security.
            ports = set([x.split(":")[-1].strip() for x in local_add_port])
            unknown_ports = filter(lambda x: x not in known_ports, ports)
            sorted_ports = map(str, sorted(map(int, unknown_ports)))
            self.ports = "+".join(sorted_ports)
        except Exception as e:
            self.err_handler.append(e)

    def query_ssh_peers(self, known_peers: Set[str]) -> None:
        """
        :param known_peers: known peer IP addresses we can safely ignore.
        """
        try:
            stdin, stdout, stderr = self.client.exec_command("ss -tn sport = 22")
            ss_lines = stdout.readlines()
            peer_add_port = find_cells_under(ss_lines, "Peer Address:Port")
            ssh_peers = set([x.split(":")[0].strip() for x in peer_add_port])
            self.ssh_peers = "+".join([x for x in ssh_peers if x not in known_peers])
        except Exception as e:
            self.err_handler.append(e)

    def query_free(self):
        try:
            stdin, stdout, stderr = self.client.exec_command("free -h")
            free_lines = stdout.readlines()
            self.mem_avail = [x for x in free_lines if x.startswith("Mem:")][0].split()[-1]
            self.swap_free = [x for x in free_lines if x.startswith("Swap:")][0].split()[-1]
        except Exception as e:
            self.err_handler.append(e)


def node_master_factory(err_handler):
    return MinerInterrogator(err_handler)


class MinerInterrogator(SSHInterrogator):
    def __init__(self, err_handler: ErrorHandler, gpu_cnt: int = 3):
        super().__init__(err_handler)
        self.g_pwr: List[Optional[str]] = [None] * gpu_cnt  # in watts
        self.g_mem: List[Optional[str]] = [None] * gpu_cnt  # in MiB
        self.g_tmp: List[Optional[str]] = [None] * gpu_cnt  # in 'C

    def do_queries(self, rmt_pc: Dict[str, Union[List[dict], str]]):
        # With paramiko/SSH, expect the unexpected, then recover and report
        # the error.
        try:
            self.initialise_connection(rmt_pc["ip"], rmt_pc["creds"])
            self.query_gpus()
            self.remote_tentative_calls(rmt_pc)
        except Exception as e:
            self.err_handler.append(e)

    @staticmethod
    def read_gpu(gpu_line: str) -> Optional[int]:
        match = re.match(r"\| +(\d+) +", gpu_line)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def read_details(details_line: str) -> Tuple[str, str, str]:
        """
        Niche enough use case that units can be omitted but we are keeping to strings.

        :param details_line:
        :return: 3-tuple of
            - temperature (C)
            - power use (W)
            - memory use (MiB)
        """
        match = re.match(r"\| +\d+% +(\d+)C +P\d +(\d+)W */ *\d+W *\| +(\d+)MiB */ *\d+MiB *\|", details_line)
        temp = match.group(1)
        pwr = match.group(2)
        mib = match.group(3)
        return temp, pwr, mib

    def query_gpus(self):
        try:
            stdin, stdout, stderr = self.client.exec_command("nvidia-smi")
            stdout_lines = stdout.readlines()
            i = 0
            while i < len(stdout_lines):
                if (re.match(r"\+-+\+-+\+-+\+\n", stdout_lines[i]) or re.match(r"\|=+\+=+\+=+\|\n", stdout_lines[i])) \
                        and i + 2 < len(stdout_lines):
                    gpu = self.read_gpu(stdout_lines[i + 1])
                    if gpu is not None:
                        temp, watts, mem_use = self.read_details(stdout_lines[i + 2])
                        self.g_pwr[gpu] = watts
                        self.g_mem[gpu] = mem_use
                        self.g_tmp[gpu] = temp
                        i += 2
                i += 1
        except Exception as e:
            self.err_handler.append(e)
