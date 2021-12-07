import pytest


@pytest.fixture
def sport22_lines():
    return """\
State              Recv-Q              Send-Q                           Local Address:Port                            Peer Address:Port               Process
ESTAB              0                   0                                 42.8.101.220:22                              61.177.173.18:26361""".split("\n")


@pytest.fixture
def free_lines_1():
    return """\
total        used        free      shared  buff/cache   available
Mem:          3.6Gi       163Mi       2.7Gi       0.0Ki       738Mi       3.2Gi
Swap:           4Gi          0B         4Gi""".split("\n")


@pytest.fixture
def ss_lines_1():
    return """\
Netid     State          Recv-Q      Send-Q           Local Address:Port             Peer Address:Port      Process
tcp       ESTAB          0           0                 42.8.101.220:22              121.44.111.12:45900
tcp       ESTAB          0           80                42.8.101.220:22              61.177.173.18:51931
tcp       FIN-WAIT-1     0           1                 42.8.101.220:22             222.186.30.112:61668""".split("\n")


@pytest.fixture
def ss_lines_2():
    return """\
Netid State    Recv-Q Send-Q Local Address:Port  Peer Address:Port Process
tcp   ESTAB    0      0       42.8.101.220:22   121.44.111.12:45900
tcp   LAST-ACK 0      81      42.8.101.220:22   61.177.173.18:29922
tcp   ESTAB    0      80      42.8.101.220:22   61.177.173.18:55557
tcp   LAST-ACK 0      1098    42.8.101.220:22   61.177.173.18:35779""".split("\n")


@pytest.fixture
def nvidia_smi_lines_1():
    return [
        'Thu Dec  9 22:30:26 2021       \n',
        '+-----------------------------------------------------------------------------+\n',
        '| NVIDIA-SMI 470.86.11    Driver Version: 470.86.11    CUDA Version: 11.4     |\n',
        '|-------------------------------+----------------------+----------------------+\n',
        '| GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |\n',
        '| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |\n',
        '|                               |                      |               MIG M. |\n',
        '|===============================+======================+======================|\n',
        '|   0  GeForce GTX 166...  Off  | 00000000:01:00.0  On |                  N/A |\n',
        '| 38%   42C    P2    77W /  78W |   4835MiB /  5944MiB |    100%      Default |\n',
        '|                               |                      |                  N/A |\n',
        '+-------------------------------+----------------------+----------------------+\n',
        '|   1  GeForce RTX 2060    Off  | 00000000:02:00.0 Off |                  N/A |\n',
        '| 57%   58C    P2   114W / 125W |   4806MiB /  5934MiB |    100%      Default |\n',
        '|                               |                      |                  N/A |\n',
        '+-------------------------------+----------------------+----------------------+\n',
        '|   2  GeForce GTX 3060    Off  | 00000000:03:00.0 Off |                  N/A |\n',
        '| 48%   66C    P2    86W /  84W |   4790MiB /  5944MiB |    100%      Default |\n',
        '|                               |                      |                  N/A |\n',
        '+-------------------------------+----------------------+----------------------+\n',
        '                                                                               \n',
        '+-----------------------------------------------------------------------------+\n']


@pytest.fixture
def mock_rmt_pc_1():
    return {
        "ip": "21.151.211.10",
        "creds": [
            {
                "username": "megamind",
                "password": "fumbledpass",
                "key_filename": "/home/megs/.ssh/id_rsa"
            }
        ]
    }


@pytest.fixture
def mock_rmt_pc_2():
    return {
        "ip": "21.151.211.11",
        "creds": [
            {
                "username": "megamind",
                "key_filename": "/home/megs/.ssh/id_rsa"
            },
            {
                "username": "segundomano",
                "password": "abracadabra",
            }
        ]
    }
