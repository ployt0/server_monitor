# Server Monitor

![python-app workflow](https://github.com/ployt0/server_monitor/actions/workflows/python-app.yml/badge.svg)

This repo helps to monitor a remote server by first checking its ping. It then attempts to SSH in and run further tests. The results are recorded in the "results" subdirectory for each month.

Nodes attempt HTTP(S) requests and record the return code and latency. This may be an assumption too far.

HTTP endpoint checks can be disabled by inheriting and overriding. [`CheckResult`](check_result.py) is the common interface.

Before server_monitor there was [server_pinger.py](server_pinger.py). It simply pings and records latency on the control node.

## Initiation

This script functions as a monitoring daemon. On a raspberry pi for example. We call this the control node, or control machine. Please ensure that this server has connected to each of the monitored nodes at least once since their provisioning.

Reinstalling a node changes its signature. SSH defaults to suspecting someone is impersonating the endpoint.

You would ok something like this:

```shell
:~$ ssh 21.151.211.10
The authenticity of host '21.151.211.10 (21.151.211.10)' can't be established.
ECDSA key fingerprint is SHA256:CjdnwQd72gf28SDGcbKFF8217261DSJcb72cb81AdwF.
Are you sure you want to continue connecting (yes/no/[fingerprint])? yes
Warning: Permanently added '21.151.211.10' (ECDSA) to the list of known hosts.
megamind@21.151.211.10: Permission denied (publickey).
```

Neglecting this will not cause an email notification to be sent. That would be annoying. Instead, observer the lack of new records (the count is in the subject) in the regular emails.

## Installation

This requires python 3.7 and above. I'll be moving to 3.9 and above asap.

Install [requirements.txt](requirements.txt) in a venv on the control machine. None of the versions are pinned. I recently (23rd July 2022) discovered that my new server was no longer reachable by paramiko, despite ansible and regular SSH having no problems. The fix was to update the package in my venv:

```shell
pip install --upgrade paramiko
```

Create a working, source, directory; eg, `mkdir ~/monitoring` on the control machine.

Copy or clone the python files, including providing a `monitored_nodes.json` (outside of source control) . Set up systemd service and timer files. The timer file specifies the interval and is named identically to the service but with the ".timer" suffix replacing ".service". For example:

```
[Unit]
Description=Timer that periodically triggers rmt-monitor.service

[Timer]
# OnCalendar=hourly
# OnCalendar=*:0/15 # okay, 15m
# OnCalendar=*-*-* *:00:00 # okay, hourly 
# OnCalendar=*-*-* 0/2:00:00 # okay, every 2 hours
OnCalendar=*-*-* 0/2:00:00
RandomizedDelaySec=2400

[Install]
WantedBy=timers.target
```

After changing the interval (less is better, for testing), do `systemctl daemon-reload`. After a pause this returns. Any parsing errors will appear in `systemctl status rmt-monitor.timer`. We can check the schedule with `systemctl list-timers`. Timers aren't scheduled *whilst* still running. Timers get their next time slot after the matching service finishes.

The unit file (*lookout!* password needed storing somewhere!):

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

Don't place these under the user's home directory: `~/.config/systemd/user/rmt-monitor.service`. This causes the timer to stop  when the user logs out.

Instead, use `/etc/systemd/system/rmt-monitor.service`. `/etc/systemd/system/` is described as, "System units created by the administrator", here: <https://www.freedesktop.org/software/systemd/man/systemd.unit.html>.

<https://askubuntu.com/a/859583> describes how "lingering" users don't cancel the timer. The consensus is to use `/etc/systemd/system/`.

`User=ployt0` underneath the `[Service]` section enables that `ployt0` user to retain ownership of the files and content residing in their home path.

Use `sudo` to copy the unit files from your home directory to `/etc/systemd/system`. This preserves unprivileged ownership. Systemd is fine with this.

In addition to running `systemctl daemon-reload` whenever advised in the output of another `systemctl` command, I can debug services (and timers) using:

```shell
systemctl start rmt-monitor
systemctl status rmt-monitor
journalctl -b -u rmt-monitor.service
```

`journalctl` is most comprehensive; all three demonstrate why systemd succeeded cron.

Add another unit file, let's say, "monitor-mailer.service", calling the same [server_mon.py](server_mon.py) but emailing (`-e`) the metrics:

```
[Unit]
Description=Emails the month's SLA stats to me.

[Service]
User=ployt0
WorkingDirectory=/home/ployt0/monitoring
ExecStart=/home/ployt0/monitoring/venv/bin/python /home/ployt0/monitoring/server_mon.py email_agent_addy@gmail.com email_agent_password -etoyoutome@gmail.com

[Install]
WantedBy=default.target
```

Schedule with "monitor-mailer.timer":

```
[Unit]
Description=Timer that periodically triggers monitor-mailer.service

[Timer]
OnCalendar=*-*-* 11:55:00

[Install]
WantedBy=timers.target
```


### JSON Nodes file

The nodes/inventory json file contains a list of machines identified by "servers", each potentially having:

```json
{
  "ip": "21.151.211.10",
  "creds": [
    {
      "username": "megamind1",
      "password": "fumbledpass1",
      "key_filename": "/home/megs/.ssh/id_rsa1"
    }
  ],
  "verify": "Optional path to public key or cert. True (default) or False to enable/disable.",
  "home_page": "Used for HTTP(S) request, as health check / heartbeat. eg 'https://example.com'",
  "ssh_peers": "IPv4 addresses of known, permitted ssh clients, separated by commas.",
  "known_ports": "known, permitted listening ports, separated by commas."
}
```

`ip`, and `creds` are required for SSH. `creds` contains `username` and either `password` or `key_filename`. `creds` are passed directly to `SSHClient.connect`. If one identity in the list fails (perhaps because the target needs to stop accepting passwords and use keys instead) the next will be tried.

`home_page` gives the exact URL to be queried requested by the `requests` library. Increasingly this will be https, and may include subdomains or paths.

The following are optional:

- `ssh_peers` allows a comma separated list of those IPs we can disregard when examining SSH sessions.

- `known_ports` is a comma separated list of ports we have accepted being open and so can be ignored by future reports.

- `verify` gets passed to `requests.get`. `verify` allows self-signing. To allow, pass the name of the cert, or False, to skip verification.

The full structure of the json nodes file (eg monitored_nodes.json) is then:

```json
{
  "servers": [],
  "email_dest": "email address to send notifications to."
}
```

### Tests

Google blocked my authentication with username and password in May 2022. It took a while to notice I wasn't getting daily emails.

The `send_email` function threw `SMTPAuthenticationError`, but had no way to report this, other than local logs.

This is why we have the CI workflow now.

### Output

The output takes the form of a line of CSV for each node under test, each time the script runs. By default, this is the `results` subdirectory, set globally as `RESULTS_DIR = "results"`.

The column names are in the `to_csv()` method, eg [CheckResult.to_csv](server_mon.py).


