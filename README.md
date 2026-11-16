# Visa Status Monitor

A lightweight Python checker for the Belgian Immigration Office's [Infovisa](https://infovisa.ibz.be/) website. It retrieves a visa application's current dossier status, converts the HTML table to JSON, and publishes the result to a self-hosted [ntfy](https://ntfy.sh/) topic.

The checker runs as a one-shot Docker Compose job, scheduled by a systemd timer.

## How it works

1. Fetches `ResultNl.aspx` using the configured diplomatic post (`PLACE`) and visa application number (`VISUMNR`).
2. Parses the response table and validates that a dossier status was found.
3. Prints the result as JSON, which can be viewed in the systemd journal.
4. Sends the **complete JSON** as the ntfy message body, with priority determined by the dossier status:

| Dossier status | ntfy priority | Meaning |
| --- | --- | --- |
| `In behandeling` | `3` (default) | Application is still being processed |
| Any other status | `4` (high) | Status needs attention; **not necessarily an approval** |

**No status file or deduplication is used.** Every successful scheduled check can publish a notification. To receive alerts only for priority **4 or higher**, configure that threshold in the ntfy subscription/client. Low-priority messages may still be published to the topic.

## Requirements

- Docker with Docker Compose
- A reachable ntfy server and topic
- A Linux host with systemd for scheduled execution
- A trusted CA certificate if the ntfy HTTPS endpoint uses a private certificate authority

## Configuration

Create a `.env` file in the project directory:

```dotenv
PLACE=DKR
VISUMNR=your-application-number

NTFY_URL=https://ntfy.example.com
NTFY_TOPIC=visum-status
NTFY_TOKEN=your-ntfy-access-token

# Required if the container uses the system CA bundle with a custom CA:
REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
```

`PLACE` is the Infovisa diplomatic-post code (for example, `DKR` for Dakar). Treat the application number and ntfy token as private information; do not commit `.env` to version control.

If your ntfy endpoint uses a private CA, place the **public CA certificate** at `certs/root-ca.crt`. The Dockerfile should copy it to `/usr/local/share/ca-certificates/` and run `update-ca-certificates`. Do not disable TLS verification with `verify=False`.

## Build and run

```bash
docker compose build
docker compose run --rm visum-status
```

The command performs one check and exits. Example JSON output:

```json
{
  "application_date": "Sep 22 2026",
  "registration_date": "Oct  1 2026",
  "status": "In behandeling",
  "decision_date": null
}
```

The example is illustrative, not a live status reading.

## Docker Compose

Example `compose.yaml`:

```yaml
services:
  visum-status:
    build: .
    env_file:
      - .env
    restart: "no"
```

No data volume is needed: the checker keeps no local status history.

## Schedule with systemd

Create `/etc/systemd/system/visum-status.service`:

```ini
[Unit]
Description=Check Belgian visa application status
Wants=network-online.target
After=network-online.target docker.service

[Service]
Type=oneshot
User=rbgtk
WorkingDirectory=/absolute/path/to/visum-status
ExecStart=/usr/bin/docker compose run --rm --no-deps visum-status
```

Replace `User` and `WorkingDirectory` with values appropriate for the host. The user must be permitted to use Docker. Build the image before running the timer, and rebuild after changing the application code or dependencies.

Create `/etc/systemd/system/visum-status.timer`:

```ini
[Unit]
Description=Check visa application status every six hours

[Timer]
OnCalendar=*-*-* 00,06,12,18:00:00
Persistent=true
Unit=visum-status.service

[Install]
WantedBy=timers.target
```

Enable the timer:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now visum-status.timer
```

Check the schedule, trigger a run manually, and view logs:

```bash
systemctl list-timers visum-status.timer
sudo systemctl start visum-status.service
journalctl -u visum-status.service -n 50 --no-pager
```

## ntfy alert filtering

Set the ntfy client's **minimum notification priority to High (4)** for this topic. This suppresses routine `In behandeling` alerts on that client while allowing high-priority status messages through. The server/topic can still receive priority-3 messages.

A high-priority notification means **the reported status is no longer `In behandeling`**. Read the actual status and decision date before interpreting it; an unexpected status or website change is not proof of approval.

## Troubleshooting

- **`status=200/CHDIR` from systemd:** Correct the service's absolute `WorkingDirectory`.
- **SSL certificate verification failure:** Verify the endpoint's certificate chain and hostname, install the issuing CA if private, and set `REQUESTS_CA_BUNDLE` to the system CA bundle inside the container.
- **No JSON status:** Verify `PLACE` and `VISUMNR`, and check whether Infovisa changed its HTML table. The checker should fail rather than report a missing status as a legitimate result.
- **No push alert:** Check that the container can reach the ntfy endpoint (including through OpenZiti if used), that the token is valid, and that the client's priority threshold is configured correctly.
- **Repeated topic messages:** Expected—there is no local status file or deduplication.

## Security notes

Keep `.env` out of Git, use HTTPS with certificate verification enabled, and avoid exposing application identifiers or notification credentials in public logs. Poll at a modest interval to avoid unnecessary load on the government website.
