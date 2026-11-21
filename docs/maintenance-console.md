# Assistant maintenance console

Start or restart the updated service once:

```bash
uv sync
uv run python -m assistant serve
```

Open **http://127.0.0.1:8765/**, using the configured port. The console shares the
existing local service; it uses local assets and requires no account, frontend build
or additional server. For another computer, use the SSH forwarding instructions in
[local service](local-service.md).

## Four views

| View | What to inspect | What to do |
| --- | --- | --- |
| 运行概览 | Last-24h executions/completions, all-time running/error roots, recent runs, next scheduled jobs and queue totals | Open a saved execution or jump into management |
| 任务编排 | Desired schedules, enabled/synchronized state, next runs and available workflows | Create/edit/pause/enable/delete a recurring plan or submit one run |
| 执行记录 | Real execution states, saved inputs, results, errors, steps and parent/child references | Filter, resume/cancel, preview and delete selected terminal records |
| Agent 调用 | Persisted provider invocations, recorded model, tokens and tools | Open the owning business step |

Execution details show business actions and results from the task and its children.
The Agent list uses traces saved at the originating step. Providers that did not
save telemetry contribute no call row. Opening a report reads local history. Notion remains the interface for proposal approval, feedback and acceptance.

## Arrange daily jobs

1. Open **任务编排 → 新建计划**, or choose **安排计划** from the workflow catalog.
2. Select a workflow and repetition: daily, weekly, monthly, hourly or custom cron.
   Monthly presets offer days 1–28; custom cron can express other dates.
3. Set the execution time and time zone. Preview lists the next five instants in
   that time zone. The overview and schedule-list next-run timestamps use your browser's
   local time, explicitly labeled in the UI.
4. Save and apply. The plan starts producing jobs when its next scheduled time arrives.
   Use **运行一次** for an immediate submission; editing a plan does not execute it.

One plan is stored per named workflow. Cron can express several trigger times, such
as `0 0 7,19 * * *`. This console arranges existing workflow entry points; those
workflows continue to own their component sequencing and human-review rules.

## Configuration and live synchronization

The selected YAML's `runtime.schedules` is the desired-state source. The console
writes only its schedule block, retaining surrounding configuration text where that
block exists. It uses atomic replacement and preserves the file mode. Provider
settings and credential values never go to the browser.

```yaml
runtime:
  schedules:
    organize-papers:
      cron: "0 0 8 * * *"
      timezone: Asia/Shanghai
      enabled: true
    organize-articles:
      cron: "0 0 9 * * 0"
      timezone: Asia/Shanghai
      enabled: false
```

A compact string such as `organize-papers: "0 0 8 * * *"` means enabled, in
Asia/Shanghai. Browser saves use the full form so pause state survives restarts.

Changes apply immediately through DBOS APIs. Startup also synchronizes desired
configuration. Removing a plan removes its Assistant-owned DBOS schedule, preserving
accepted executions and history. No automatic backfill is enabled. Unchanged plans
retain their firing metadata.

After manually editing the YAML, click **同步配置** to apply it without restarting.
The panel shows mismatches as **待同步**, including scheduler entries awaiting removal.
If configuration is saved but DBOS synchronization fails, the API reports that split
explicitly; **同步配置** retries the saved desired state. Stale forms are rejected by
revision checking so they cannot silently overwrite newer edits. Reopen the editor
when another browser or a local edit changed the configuration.

An in-progress schedule trigger may already have submitted a job when you pause or
delete its plan. Existing jobs continue. Pausing controls future triggers; cancelling
an execution is a separate operation. Provider/model/service-port changes still need
service restart.

## Inspect and clean up execution

Use **执行记录** to search and filter. **查看 / 清理错误记录** selects all-time ERROR
and MAX_RECOVERY_ATTEMPTS_EXCEEDED records, including children. Select individual
records or the current page, up to 50 per maintenance request, then preview deletion.

The preview lists allowed records and protection reasons. Deletion removes selected
DBOS execution records and their checkpoints. Child records remain unless explicitly
selected. Active Workbench owners, referenced checkpoints, active dependencies and
shared successful recommendation caches are retained. A changed preview requires
review again. No Notion page, source material or business-index record is deleted.

**恢复执行** uses the existing code-version guard and durable recovery queue.
**取消任务** targets that execution only. An already-running external call may return
before cancellation takes effect at subsequent DBOS boundaries; children are not
cancelled recursively. No button rewrites a saved result to pretend execution succeeded.

DBOS SUCCESS describes function completion. A successful proposal workflow may still
be awaiting human approval in Notion; inspect the saved result for business state.

## Where to change the console

The UI uses native browser modules under `src/assistant/runtime/service/web/`:
`overview.js`, `schedules.js`, `executions.js` and `agents.js` correspond to the
four navigation views. `app.js` owns navigation/refresh; `ui.js` provides shared
controls and the local API client. `index.html` holds layout and forms; styles are
local CSS. There is no Node build or separate frontend service.

`runtime/service/scheduling.py` owns online configuration/scheduler synchronization.
`monitoring.py` reads saved executions, `metadata.py` isolates read-only system-table
queries, and `administration.py` owns explicit execution maintenance. Business
workflows remain in their existing task and step modules.

Open a schedule row for its time zone, Cron expression, upcoming runs and
maintenance actions. Open an agent call row to inspect input, output, token
counts and tools. Both detail sheets support keyboard selection and Escape.
