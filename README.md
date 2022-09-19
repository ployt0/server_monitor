# Server Monitor

![python-app workflow](https://github.com/ployt0/server_monitor/actions/workflows/python-app.yml/badge.svg)

This repo helps to monitor a remote server by first checking its ping.
It then attempts to SSH in and run further tests. The results are recorded
in the "results" subdirectory for each month and node type.

Currently, there are 2 node types: miner and ordinary node. The Ordinary
node type attempts HTTP requests and records the return code and latency.
This may be an assumption too far. Miner node prefers instead to query
`nvidia-smi` collecting: power use, memory use, and temperatures.

HTTP endpoint checks can be disabled by inheriting and overriding.
[`ChecksInterface`](checks_interface.py) is the lowest denominator and 
[server_mon.py](server_mon.py) implements this as `CheckResult`, along with
other role-specific functionality.

The starting point for this project was [server_pinger.py](server_pinger.py).
It simply pings are records latency on the control node.

## Installation

Install [requirements.txt](requirements.txt) in a venv on the control machine.
None of the versions are pinned and I recently discovered that my new server
was no longer reachable by paramiko, despite ansible and regular SSH having
no problems. The fix was to update the package in my venv:

```shell
pip install --upgrade paramiko
```

Create a working, source, directory; eg, `mkdir ~/monitoring` on the 
controlling machine.

Copy or clone the python files, especially [server_mon.py](server_mon.py)
and your (outside of source control) `monitored_nodes.json`. Set up systemd
service and timer files. The timer file specifies the interval and is named
identically to the service but with the ".timer" suffix replacing ".service".
For example:

```
[Unit]
Description=Timer that periodically triggers rmt-monitor.service

[Timer]
# OnCalendar=hourly
# OnCalendar=*:0/15 # okay, 15m
# OnCalendar=*-*-* *:00:00 # okay, hourly 
# OnCalendar=*-*-* 0/2:00:00 # okay, every 2 hours
RandomizedDelaySec=2400

[Install]
WantedBy=timers.target
```

After changing the interval (3 minutes is good for testing), do 
`systemctl daemon-reload`. After a pause this returns.
Any parsing errors will appear in `systemctl status rmt-monitor.timer`.
We can check the schedule with `systemctl list-timers`. Timers aren't scheduled 
*whilst* still running. Timers get their next time slot after the matching
service finishes.

The unit file (lookout, password needed storing somewhere!):

```
[Unit]
Description=Collects SLA stats for my remote servers.

[Service]
User=ployt0
WorkingDirectory=/home/ployt0/monitoring
ExecStart=/home/ployt0/monitoring/venv/bin/python /home/ployt0/monitoring/server_mon.py email_agent_addy@gmail.com email_agent_password

[Install]
WantedBy=default.target
```

Don't start as I began, by placing these in the user home subdirectory, like
`~/.config/systemd/user/rmt-monitor.service`.  Doing so causes the timer to stop
when the user logs out. It may resume upon re-login but that leaves gaps.
Instead, use `/etc/systemd/system/rmt-monitor.service`. `/etc/systemd/system/`
is described as, "System units created by the administrator", here:
<https://www.freedesktop.org/software/systemd/man/systemd.unit.html>.

<https://askubuntu.com/a/859583> describes how "lingering" my user
could have prevented service interruption. A year older, <https://askubuntu.com/a/676022>
states the opposite, which is what I did, after a brief flirtation with the
*new* ideas.

`User=ployt0` underneath the `[Service]` section enables that user to retain
ownership of the files and content residing in their home path.

Use `sudo` to copy files to `/etc/systemd/system` so as to preserve
unprivileged ownership. Systemd is fine with this.

In addition to running `systemctl daemon-reload` whenever advised in the output
of another `systemctl` command, I can debug services (and timers) using:

```shell
$ systemctl start rmt-monitor
$ systemctl status rmt-monitor
$ journalctl -b -u rmt-monitor.service
```

The one about `journalctl` is my favourite but all three help make the case for
preferring systemd to cron.

Now to add another unit file, let's say, "monitor-mailer.service", calling the
same [server_mon.py](server_mon.py) but emailing the metrics, for the month:

```
ExecStart=/home/ployt0/monitoring/venv/bin/python /home/ployt0/monitoring/server_mon.py email_agent_addy@gmail.com email_agent_password -etoyoutome@gmail.com
```

### JSON Nodes file

The nodes/inventory json file contains a list of machines identified by
"servers", each potentially having:

```json
{
    "ip": "21.151.211.10",
    "creds": [
      {
        "username": "megamind",
        "password": "fumbledpass",
        "key_filename": "/home/megs/.ssh/id_rsa"
      }
    ],
    "home_page": "optional path component of URL to request.",
    "ssh_peers": "IPv4s of known, permitted ssh clients, separated by commas.",
    "known_ports": "known or permitted listening ports, separated by commas."
}
```

`ip`, and `creds` are required for SSH. `creds` contains `username` and either
`password` or `key_filename`. `creds` are passed directly to 
`SSHClient.connect`. If one identity in the list fails (perhaps because the
target needs to stop accepting passwords and use keys instead) the next will
be tried.

`home_page` gives the exact URL to be queried requested by the `requests`
library. Increasingly this will be https, and may include subdomains or paths.
Hence the IP address alone is insufficient.

The following are optional:

- `ssh_peers` allows a comma separated list of those IPs we can disregard when
  examining SSH sessions.

- `known_ports` is a comma separated list of ports we have accepted being open
  and so can be ignored by future reports.

The full structure of the json nodes file (eg monitored_nodes.json) is then:

```json
{
  "servers": [],
  "this_ip": "ip address of testing machine, to exclude from peers list.",
  "email_dest": "email address to send notifications to."
}
```

### Tests

Google stopped allowing simple log in with username and password in May 2022.
This caused the script to proceed (succeed) without sending any emails.

The `send_email` function threw `SMTPAuthenticationError` but had no way to
report this other than local logs.

For that reason integration testing is advisable.


