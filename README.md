# Server Monitor

![python-app workflow](https://github.com/ployt0/server_monitor/actions/workflows/python-app.yml/badge.svg)

This repo helps to monitor a remote server by first checking its ping.
It then attempts to SSH in and run further tests. The results are recorded
in the "results" subdirectory for each month and node type.

Currently there are 2 node types: miner and ordinary node. Ordinary node
assumes it will be serving http and records the return code and latency.
This may be an assumption too far. Miner node prefers instead to query
`nvidia-smi` collecting power use, memory use, and temperatures.

HTTP endpoint checks can be disabled by inheriting and overriding.
[`ChecksInterface`](checks_interface.py) is the lowest denominator and 
[server_mon.py](server_mon.py) implements this as `CheckResult`, along with
other role-specific functionality.

The starting point for this project was [server_pinger.py](server_pinger.py).
It simply pings are records latency on the control node.

## Installation

Install requirements in a venv on the control machine.

Create a working, source, directory; eg, `mkdir ~/monitoring` on the 
controlling machine.

Copy or clone the python files, especially [server_mon.py](server_mon.py)
and your (outside of source control) `monitored_nodes.json`. Set up systemd unit
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
`systemctl daemon-reload`, after a pause this returns.
Any parsing errors will appear in `systemctl status rmt-monitor.timer`.
We can check the schedule with `systemctl list-timers`. It won't be scheduled 
*whilst* it is still running, it gets its next time slot after the matching
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

Don't be lulled into placing these in the user home subdirectory like
`~/.config/systemd/user/rmt-monitor.service`.  Doing so causes the timer to stop
when the user logs out. It may resume upon re-login but that leaves gaps.
Instead, use `/etc/systemd/system/rmt-monitor.service`. `/etc/systemd/system/`
is described as, "System units created by the administrator", here:
<https://www.freedesktop.org/software/systemd/man/systemd.unit.html>.

`User=ployt0` underneath the `[Service]` section enables that user to retain
ownership of the files and content residing in their home path.

I chose to use the user home subdirectory initially, because people raved 
about it. <https://askubuntu.com/a/859583> describes how "lingering" my user
could have prevented this. A year older, <https://askubuntu.com/a/676022>
states the opposite, which is what I did, after a brief flirtation with the
*new* ideas.

Beginning in the home directory was one way for my user to retain file
ownership, even after copying to `/etc/systemd/system`. Systemd still works 
with them.

In addition to running `systemctl daemon-reload` whenever advised in a
command's output, I can debug services (and timers) using:

```shell
$ systemctl start rmt-monitor
$ systemctl status rmt-monitor
$ journalctl -b -u rmt-monitor.service
```

The one about `journalctl` is my favourite but all three help make the case for
preferring systemd to cron.

Now to add another unit file, let's say, "monitor-mailer.service", calling the
same [server_mon.py](server_mon.py) but emailing the metrics, for the day:

```
ExecStart=/home/ployt0/monitoring/venv/bin/python /home/ployt0/monitoring/server_mon.py email_agent_addy@gmail.com email_agent_password -etoyoutome@gmail.com
```

### JSON Nodes file

The nodes/inventory file is a list of machines described in json as:

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
    "http_target": "optional path component of URL to request.",
    "ssh_peers": "known or permitted ssh clients, separated by commas.",
    "known_ports": "known or permitted listening ports, separated by commas."
}
```

`ip`, and `creds` are required for SSH. `creds` contains `username` and either
`password` or `key_filename`. `creds` are passed directly to 
`SSHClient.connect`. If one identity in the list fails (perhaps because the
target needs to stop accepting passwords and use keys instead) the next will
be tried.

The following are optional:

- `http_target` allows a path below the domain root to be requested with HTTP.

- `ssh_peers` allows a comma separated list of those IPs we can disregard when
  examining SSH sessions.

- `known_ports` is a comma separated list of ports we have accepted being open
  and so can be ignored by future reports.