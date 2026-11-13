# Local execution service

The dedicated host runs one `serve` process. It owns DBOS, providers, durable queues,
schedules and recovery. CLI commands submit requests or query saved reports over
loopback HTTP. No Conductor subscription, account registration or container is needed.

The [service sequence diagrams](service-sequences.md) show submission, execution,
inspection and recovery across the local processes. The root Drawio file describes business information flow.

## Start and submit

Install the updated dependencies once:

```bash
uv sync
```

Start the service in terminal A:

```bash
uv run python -m assistant serve
```

Use terminal B for normal commands:

```bash
uv run python -m assistant run propose-tasks
uv run python -m assistant run organize-papers --page NOTERO_PAGE_ID
uv run python -m assistant run process-workbench
uv run python -m assistant status
```

`run` waits for a saved business result and prints the same JSON report as before.
Providers and detailed execution logs now run in the serve terminal and its configured
log files. The client reports submission and status transitions. `-v` changes detail;
configured log levels continue to determine which records appear.

For IDE debugging, start `serve` under the debugger and submit jobs from another
terminal. Breakpoints remain in the existing workflow, step and component functions.
The service is foreground by default; keep its terminal open or supervise the same
command using your host's service manager for unattended operation.

## Detach, inspect and recover

```bash
uv run python -m assistant run recommend-papers --detach
uv run python -m assistant status WORKFLOW_ID
uv run python -m assistant status WORKFLOW_ID --result
uv run python -m assistant status --limit 50
uv run python -m assistant resume WORKFLOW_ID
uv run python -m assistant resume WORKFLOW_ID --detach
```

A detached request returns a durable workflow ID after the queue commit. `status ID`
includes checkpoints and child IDs; `status ID --result` returns the saved result or
error, without rerunning work. For active tasks it returns their current state.
Default status lists 20 recent workflows and registered schedules.

Ctrl+C in a waiting client stops waiting. Accepted execution continues in serve.
A failed task makes a waiting run/resume command exit with an error. After correcting
its cause, resume the recorded ID. An active or successful workflow is observed rather
than restarted. A recovery receipt may identify a separate durable recovery workflow;
its result is the original task result. Inspect the original ID for business steps.

The CLI prints a request UUID before submission. If the connection fails before an
acknowledgement, retry the same job/page and UUID to find or submit that one request:

```bash
uv run python -m assistant run organize-papers --page PAGE_ID --request-id REQUEST_UUID
uv run python -m assistant resume WORKFLOW_ID --request-id REQUEST_UUID
```

Reusing a submission UUID never reruns a completed dispatch; different job/page
arguments with that UUID are rejected. A fresh UUID submits a new dispatch, whose
business workflows still apply their own source-version and daily-edition deduplication.

## Configuration and shutdown

```yaml
runtime:
  directory: data/assistant
  service:
    port: 8765
  schedules: {}
```

Serve and clients use the same configuration. With a custom file, place `--config`
before the command in both terminals. Clients use the running service's providers;
restart serve after changing provider, schedule or model settings.

HTTP binds to `127.0.0.1` only. Each client supplies the resolved runtime directory;
the server rejects requests targeting another data directory on the same port. This
is a configuration guard, not user authentication. Keep the endpoint local. Multiple
isolated runtimes require distinct directories and ports. Only one process may own
one runtime directory.

Only serve starts DBOS and automatic compatible-work recovery. Client commands never
open the application database. Stop serve before `setup`; setup performs explicit
Notion schema preparation and does not start or recover DBOS tasks.

Stop serve with Ctrl+C or SIGTERM. HTTP stops accepting requests, then DBOS gets up
to 10 seconds to finish active work. Use the same configuration and code version on
restart to recover persisted unfinished executions. Successful checkpoints are reused;
external effects interrupted before checkpoint commit may repeat. Version guards stay
enabled, and incompatible unfinished work requires explicit handling.

Manual and scheduled dispatch share `assistant-jobs` (one worker slot). Schedule
callbacks use `assistant-triggers` and enqueue the same business dispatch. Recovery
requests use `assistant-recovery`, which can wait for recovered work without occupying
its business slot. Business queue identity is retained when explicitly recovering a
queued workflow. Older interrupted workflows may retain their original execution
structure; this change does not rewrite existing state.

## Local API for the future report page

All requests supply `X-Assistant-Runtime` with the absolute `runtime.directory/v2` path.
The API reports DBOS execution states; Notion approval and acceptance remain business
states and are not inferred from DBOS SUCCESS.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Service/runtime identity and code version |
| POST | `/jobs` | Submit `{job, page?, request_id?}`; return durable ID |
| GET | `/status?limit=20` | Recent workflows and schedules |
| GET | `/jobs/{id}` | Saved execution metadata |
| GET | `/jobs/{id}/steps` | Checkpoints and child workflow references |
| GET | `/jobs/{id}/result` | Saved report/error, or active state |
| GET | `/schedules` | Registered schedule definitions |
| POST | `/workflows/{id}/resume` | Submit recovery with `{request_id?}` |

This is the backend for a later report page. The current release provides JSON
inspection through CLI; no report frontend has been added.

## Optional unattended Linux host

For a dedicated host, a [systemd user unit](../deploy/systemd/agentic-assistant.service)
runs the same foreground serve command under your existing account. It uses the
same home directory, Codex login and local configuration. No service is installed
or started automatically by the project.

First check the unit's WorkingDirectory/ExecStart against your checkout location.
Stop any manually started serve process, then install the unit:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd/agentic-assistant.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now agentic-assistant
systemctl --user status agentic-assistant
journalctl --user -u agentic-assistant -f
```

A user service has a different shell environment from your interactive terminal.
If needed, create `~/.config/agentic-assistant/service.env` with the PATH containing
Codex/Node and any proxy environment variables used by the host. Alternatively,
set `codex.executable` to the installed executable's absolute path in local YAML.
Restart the service after changing these settings.

To keep user services running after logout and start them at boot, enable lingering
for your account using `loginctl enable-linger "$USER"` (host permissions may require
an administrator). This is a host administration choice, separate from task scheduling.

For setup or IDE debugging, stop the background service first:

```bash
systemctl --user stop agentic-assistant
uv run python -m assistant setup
# Or start serve under the IDE debugger, then use CLI clients from another terminal.
systemctl --user start agentic-assistant
```
