"""Define command-line usage, workflow selection, and task-specific help."""

from pathlib import Path
import argparse

JOB_HELP = {
    "propose-tasks": {
        "help": "Draft Workbench proposals from Inbox and elevated TODO items.",
        "description": (
            "Read eligible Notion inputs, draft proposals, and submit them to Workbench\n"
            "for human approval. This job does not execute the newly proposed tasks."
        ),
        "epilog": """Inputs and writes:
  Inbox: Status != Archived. TODO: Status = elevated.
  After verified proposal publication, mark Inbox Archived or TODO handled.
  Unchanged managed inputs reuse their existing proposal instead of redrafting.

Next step:
  Review the proposal in Notion. Set Human Review to Approved, Revision Requested,
  or Rejected; put planning feedback in Human Instruction. Then run process-workbench.

Examples:
  python -m assistant run propose-tasks
  python -m assistant --config config.local.yaml run propose-tasks
  python -m assistant run process-workbench""",
    },
    "process-workbench": {
        "help": "Process human decisions, execute approved work, and curate accepted results.",
        "description": (
            "Read human decisions for locally managed Workbench items and advance each\n"
            "eligible item to its next review boundary. Also turn Interested Research\n"
            "Feed entries into deduplicated Inbox follow-ups, never directly into Papers."
        ),
        "epilog": """Human review transitions:
  Open / Approved           Route and execute the approved task; save Executed.
  Open / Revision Requested Revise the proposal; return to Pending approval.
  Open / Rejected           Mark Deprecated.
  Executed / Unqualified    Redo using Result Feedback; request acceptance again.
  Executed / Qualified      Curate into Knowledge / Ideas, then Archived;
                            without reusable output, mark Finished instead.

Scope and writes:
  Only items registered in the local workflow index are managed; old Notion rows
  are not imported automatically. Pending decisions remain waiting.
  Changed source content requires a revised proposal rather than executing the
  old approval. Missing user-owned information returns the task to Pending.
  This job can call models and write Notion reports, statuses, and retained outputs.

Examples:
  python -m assistant run process-workbench
  python -m assistant --config config.local.yaml run process-workbench

Approve and accept results in Notion; this command does not approve them for you.""",
    },
    "organize-papers": {
        "help": "Organize read-only Notero captures into paper briefs or proposals.",
        "description": (
            "Read raw Zotero-synced records from Notero and organize the supplied\n"
            "material into Papers briefs. Inputs needing further investigation or\n"
            "human decisions are submitted as Workbench proposals instead."
        ),
        "epilog": """Inputs and writes:
  Notero is the raw source; Papers is the organized output, not the input library.
  Notero remains read-only. Existing human titles and notes in Papers are retained
  while the assistant-owned brief is updated. Source / Zotero URI / DOI matching
  avoids duplicate paper outputs.

Batch and reading scope:
  Without --page, select up to runtime.batch_size pending inputs (default: 20).
  Compare queried page revisions with the local handled index before reading bodies.
  Unchanged handled pages are skipped; changed content is checked again.
  Advance the cursor after batch success. Notero receives no bookkeeping writes.
  --page checks one raw Notero page without moving the collection cursor.
  Unchanged content is still skipped; --page is not a force-regenerate option.
  Zotero attachments are not downloaded. Abstracts and notes are not full-text reads.

Examples:
  python -m assistant run organize-papers
  python -m assistant run organize-papers --page NOTERO_PAGE_ID
  python -m assistant --config config.local.yaml run organize-papers""",
    },
    "organize-articles": {
        "help": "Organize independent SimpRead captures into briefs, knowledge, or proposals.",
        "description": (
            "Read captured articles from the independent SimpRead Notion database.\n"
            "Classify supplied material into Papers, Knowledge, or a Workbench proposal\n"
            "when additional investigation or a human decision is required."
        ),
        "epilog": """Inputs and writes:
  Normal scans select captures with Agent Archived unchecked.
  Verify the destination before marking the source Agent Archived.
  Preserve existing human notes when updating organized paper briefs.

Batch and reprocessing:
  Without --page, read up to runtime.batch_size pending captures (default: 20).
  Start at the pending queue head on each run, since archiving removes query rows.
  --page checks one raw SimpRead page, including an already archived capture,
  without moving the collection cursor. Unchanged content is still skipped;
  this is not a force-regenerate option.
  The source database must already have the Agent Archived checkbox property.

Examples:
  python -m assistant run organize-articles
  python -m assistant run organize-articles --page SIMPREAD_PAGE_ID
  python -m assistant --config config.local.yaml run organize-articles""",
    },
    "recommend-papers": {
        "help": "Assess research candidates within evidence gates and daily maxima.",
        "description": (
            "Discover candidates, read available primary evidence, assess relevance,\n"
            "and report selections, rejections, source failures, and publications.\n"
            "The current discovery provider is an offline demo; AMiner is not connected."
        ),
        "epilog": """Current demo behaviour:
  With providers.discovery: demo, use synthetic candidates and fixed assessments.
  Demo mode does not read real research interests, call the recommendation model,
  or publish synthetic papers to Research Feed. Selection is not publication.

Evidence and limits:
  Mainline Deep Read requires complete primary text. Keep author claims,
  experimental support, and agent inference separate; no graphical abstracts.
  runtime.recommendation_maxima sets per-category upper bounds (default: one each
  for Understanding Daily, Mainline Deep Read, Frontier Radar, Exceptional Event).
  Zero recommendations is valid. Interests and Human Feedback remain unchanged.

Persistence and output:
  Use the current Asia/Shanghai date. Repeat runs on the same day and mode reuse
  the same workflow result; they do not force a new search or model evaluation.
  Print a JSON report and save it under runtime.directory/recommendations/.
  To retry a failed run, use status to find its ID, then resume WORKFLOW_ID.

Examples:
  python -m assistant run recommend-papers
  python -m assistant --config config.local.yaml run recommend-papers
  python -m assistant status""",
    },
}


def arguments() -> argparse.Namespace:
    """Parse commands without opening configuration, models, or the DBOS runtime.

    Returns:
        Command options, including the selected job and optional raw page ID.
    """
    formatter = argparse.RawDescriptionHelpFormatter
    verbose_options = argparse.ArgumentParser(add_help=False)
    verbose_options.add_argument(
        "-v", "--verbose", action="store_true", default=argparse.SUPPRESS,
        help="Include workflow/page IDs, query keys, and full tracebacks; keep log levels unchanged.",
    )
    parser = argparse.ArgumentParser(
        prog="agentic-assistant",
        formatter_class=formatter,
        description=(
            "Run a personal research assistant with Notion inputs and human review.\n"
            "DBOS persists workflow progress so completed steps can be reused on recovery."
        ),
        epilog="""Configuration:
  Read providers, models, credentials, batch limits, and schedules from YAML.
  Put --config FILE before COMMAND. Dotted CLI configuration overrides are not supported.
  runtime.directory selects the local DBOS database and source index
  (default: data/assistant, relative to the current working directory).

Runtime behaviour:
  Commands using the same runtime directory require exclusive access: stop serve
  before running another command. Launching DBOS can recover previously unfinished
  work, including during status or setup. Help exits before launching the runtime.

Logging:
  Log levels select which records are emitted; -v does not change those levels.
  Add -v or --verbose before or after the command/job for diagnostic fields,
  token usage details, and full exception tracebacks on emitted records.
  JSON business results on stdout are unchanged.

Examples:
  python -m assistant run propose-tasks
  python -m assistant run process-workbench -v
  python -m assistant run organize-papers --help
  python -m assistant --config config.local.yaml run process-workbench
  python -m assistant serve

The agentic-assistant console command accepts the same arguments.
Use COMMAND --help or run JOB --help for detailed behaviour and examples.""",
    )
    parser.add_argument(
        "--config", type=Path, metavar="FILE",
        help="YAML configuration file (default: config.yaml in the assistant package); place before COMMAND.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Include workflow/page IDs, query keys, and full tracebacks; keep log levels unchanged.",
    )
    commands = parser.add_subparsers(dest="command", required=True, title="commands", metavar="COMMAND")

    # Job subcommands retain existing invocation syntax while exposing their own help.
    run = commands.add_parser(
        "run", help="Run one named job once, print its result, and exit.",
        formatter_class=formatter, parents=[verbose_options],
        description=(
            "Run one named workflow pass without enabling recurring schedules.\n"
            "The job may call models and update Notion; human approval boundaries remain."
        ),
        epilog="""Options and configuration:
  Select a job below; run JOB --help describes its sources, writes, and examples.
  --page PAGE_ID is available only for organize-papers and organize-articles.
  Configure providers, model settings, and batch limits in YAML, not as CLI overrides.
  Previously unfinished workflows can also recover when DBOS starts.

Examples:
  python -m assistant run propose-tasks
  python -m assistant run process-workbench
  python -m assistant run organize-papers --page NOTERO_PAGE_ID
  python -m assistant run recommend-papers --help

Use serve for recurring schedules, or resume WORKFLOW_ID to recover a failed run.""",
    )
    run.set_defaults(page=None)
    jobs = run.add_subparsers(dest="job", required=True, title="jobs", metavar="JOB")
    for name, documentation in JOB_HELP.items():
        job = jobs.add_parser(name, formatter_class=formatter, parents=[verbose_options], **documentation)
        if name in {"organize-papers", "organize-articles"}:
            job.add_argument(
                "--page", metavar="PAGE_ID",
                help=(
                    "Check one raw Notion page ID instead of the next batch "
                    "(default: pending-input batch). Unchanged content remains deduplicated."
                ),
            )

    commands.add_parser(
        "serve", help="Stay running and dispatch schedules explicitly enabled in YAML.",
        formatter_class=formatter, parents=[verbose_options],
        description=(
            "Start the persistent DBOS scheduler and keep this process running.\n"
            "Dispatch only jobs listed in runtime.schedules; each execution uses the\n"
            "same workflows and human-review boundaries as a manual run."
        ),
        epilog="""Schedule configuration:
  runtime:
    schedules:
      propose-tasks: "0 0 7 * * *"
      process-workbench: "0 */15 * * * *"

  Use six cron fields: second minute hour day-of-month month day-of-week.
  Timezone: Asia/Shanghai. The example proposes tasks at 07:00 and processes reviews every
  15 minutes. With schedules: {} (default), the process waits without new jobs.
  Available jobs: propose-tasks, process-workbench, organize-papers,
  organize-articles, recommend-papers.

Persistence and shutdown:
  Schedules persist in DBOS. This command updates configured schedules and pauses
  assistant-* schedules removed from YAML. Missed offline runs are not backfilled.
  Already-started unfinished workflows may recover on launch.
  Press Ctrl+C to stop; shutdown allows active workflows up to 10 seconds to finish.
  Do not run a second command against the same runtime directory while serving.

Examples:
  python -m assistant serve
  python -m assistant --config config.local.yaml serve

Use run JOB to debug a single pass before enabling a schedule.""",
    )
    commands.add_parser(
        "status", help="Print saved schedules and the 20 most recent workflow statuses.",
        formatter_class=formatter, parents=[verbose_options],
        description=(
            "Print JSON containing persisted schedules and the 20 most recent workflows.\n"
            "Workflow entries include id, status, and name; inputs and outputs are not loaded."
        ),
        epilog="""Runtime behaviour:
  Read the database selected by runtime.directory in the active YAML configuration.
  This is not an offline database viewer: DBOS starts first and may recover
  previously unfinished work, including operations that write to Notion.
  The same exclusive runtime lock applies; stop serve before using this command.

Examples:
  python -m assistant status
  python -m assistant --config config.local.yaml status

Use a workflow id from this output with resume WORKFLOW_ID after fixing its error.""",
    )
    resume = commands.add_parser(
        "resume", help="Recover an existing workflow using its saved checkpoints.",
        formatter_class=formatter, parents=[verbose_options],
        description=(
            "Recover the selected workflow rather than starting a new business task.\n"
            "For ERROR workflows, rewind from the failed step and retain earlier successful\n"
            "checkpoints; recover failed child workflows first when recorded. Other states\n"
            "use DBOS resume. Completed workflows are not forced to run again."
        ),
        epilog="""Requirements and effects:
  Use the original runtime.directory and compatible provider configuration.
  Find the workflow ID with status, inspect the error, and correct its cause first.
  Retried operations may call a model or write Notion. Cached successful steps
  are reused, but operations interrupted before checkpoint commit may repeat.
  Changed source content or human authorization still blocks outdated writes;
  resume does not grant approval or bypass the Notion review workflow.

Examples:
  python -m assistant status
  python -m assistant resume WORKFLOW_ID
  python -m assistant --config config.local.yaml resume WORKFLOW_ID

Use run process-workbench for newly recorded human decisions, not resume.""",
    )
    resume.add_argument(
        "workflow_id", metavar="WORKFLOW_ID",
        help="Exact existing workflow ID from status, in the configured DBOS database.",
    )
    commands.add_parser(
        "setup", help="Explicitly add required Notion schema fields and status options.",
        formatter_class=formatter, parents=[verbose_options],
        description=(
            "Initialize the Notion schema additions needed by the configured stores.\n"
            "This command modifies database structure; it is not a connection-only check."
        ),
        epilog="""Schema additions:
  Workbench: add Finished to Status, Publication Key text, and Proposal Version number.
  Workbench: also add Source Kind and Execution Error text properties.
  Knowledge / Ideas: add the Archive Key rich-text property when configured.
  Papers / Knowledge: add the Publication Key rich-text property for brief receipts.
  Inbox: add the Research Feed Key rich-text property.
  Existing additions are retained; successful writes are independently read back.

Scope and prerequisites:
  Configure the Notion token and data source IDs in YAML, and grant the integration
  access to those databases. SimpRead must already have Agent Archived as a checkbox;
  setup does not create that field or create missing databases.
  Existing properties and rows are preserved; no migration or new model job is requested.
  DBOS still starts and can recover previously unfinished workflows.

Examples:
  python -m assistant setup
  python -m assistant --config config.local.yaml setup

Run once on a new workspace or after required schema changes, not before every job.""",
    )
    options = parser.parse_args()
    return options
