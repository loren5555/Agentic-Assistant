"""Define command-line usage, workflow selection, and task-specific help."""

from pathlib import Path
import argparse

JOB_HELP = {
    "propose-tasks": {
        "help": "Organize Inbox and elevated TODO inputs and propose work.",
        "description": (
            "Read pending source versions through independent processors. Shared Organizer and\n"
            "Proposer submit Workbench proposals. No execution or final knowledge publication."
        ),
        "epilog": """Sources:
  Inbox Status != Archived; TODO Status = elevated; Agent Processed unchecked.
  After verified proposal publication, acknowledge the same source version.
  Review and approve the proposal, then run process-workbench.

Example:
  python -m assistant run propose-tasks""",
    },
    "organize-papers": {
        "help": "Prepare Workbench proposals from pending Notero papers.",
        "description": (
            "Read raw Notero papers, organize their supplied evidence and propose reading work.\n"
            "Papers publication happens after execution and acceptance, not during intake."
        ),
        "epilog": """Sources and outputs:
  Agent Processed unchecked selects pending Notero inputs. --page checks one record.
  Publication retains Papers reading metadata and human notes. Agent In Papers is
  checked only after successful Papers publication. Attachments are not downloaded.

Example:
  python -m assistant run organize-papers --page NOTERO_PAGE_ID""",
    },
    "organize-articles": {
        "help": "Prepare work and knowledge proposals from pending SimpRead clips.",
        "description": (
            "SimpRead Processor reads clips and user notes. Shared Organizer identifies useful\n"
            "knowledge and actionable findings; Proposer submits them to Workbench."
        ),
        "epilog": """Sources and outputs:
  Read Agent Archived unchecked and Agent Processed unchecked.
  Acknowledge after proposal publication, not after downstream execution.
  A source can lead to multiple accepted Knowledge, Papers, Ideas or Interests outputs.
  Reconciled feedback reopens the same source with a new version.

Example:
  python -m assistant run organize-articles""",
    },
    "process-signals": {
        "help": "Propose work from Interested papers/feed and explicit interest requests.",
        "description": (
            "Read Papers Interested, Research Feed Interested, and research interests marked\n"
            "Agent Pending through source-specific processors and the shared proposal path."
        ),
        "epilog": """No Inbox copies are created. Ordinary Active research interests are used by
recommend-papers without automatically generating proposals.

Example:
  python -m assistant run process-signals""",
    },
    "reconcile-feedback": {
        "help": "Return clarification answers and review feedback to their original sources.",
        "description": (
            "Collect managed Workbench feedback. Append human supplements and historical work\n"
            "links to the source, advance its version and reopen it. No model or worker is called."
        ),
        "epilog": """Transitions:
  Needs Input: answer in Human Instruction, then select Revision Requested or Approved.
  Submitted answers: source v+1; old clarification Superseded; run its source job again.
  Unanswered clarification proposals remain waiting.
  Revision Requested / Unqualified: source v+1; old work Superseded.
  Rejected: old work Deprecated, with no new source version.
  Run the original source job next, then review and approve its fresh proposal.
  Retries of the same feedback round do not increment the version again.

Example:
  python -m assistant run reconcile-feedback""",
    },
    "process-workbench": {
        "help": "Reconcile feedback, execute approvals and publish accepted outputs.",
        "description": (
            "First reconcile revisions/rejections. Execute each approved proposal's saved\n"
            "workflow and return its result for review. Qualified plans create fresh execution\n"
            "proposals; other accepted results are curated and published."
        ),
        "epilog": """Transitions:
  Needs Input: wait for an answer; submitted answers return to the source first.
  Open / Approved: use the saved workflow; result becomes Executed / Pending.
  plan / Executed / Qualified: finish planning and propose execution for fresh approval.
  Executed / Qualified: retain useful outputs, then Archived; otherwise Finished.
  Revision Requested / Unqualified: reopen source, never directly redo a worker.
  Rejected: Deprecated. Pending approvals and acceptance remain waiting.

Outputs:
  Papers, Knowledge, Ideas and Research Interests share the acceptance boundary.
  Interested recommendation input belongs to process-signals.

Example:
  python -m assistant run process-workbench""",
    },
    "recommend-papers": {
        "help": "Autonomously discover, assess and publish daily paper recommendations.",
        "description": (
            "Read research interests, discover candidates, retrieve evidence and evaluate\n"
            "relevance. Recommendations publish directly to Research Feed, outside Workbench."
        ),
        "epilog": """Scope:
  Daily recommendation maxima are caps, not quotas. Mainline Deep Read requires
  complete primary text. Missing evidence is reported, not fabricated.
  With discovery: demo, use offline fixtures and never publish synthetic entries.
  Same-day retries reuse their durable report. Interested feedback later enters
  process-signals and the normal proposal path.

Examples:
  python -m assistant run recommend-papers
  python -m assistant run process-signals""",
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
  (default: data/assistant/v2; v0.1 databases remain untouched).

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
  organize-articles, process-signals, reconcile-feedback, recommend-papers.

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
  Workbench: add Finished, Superseded and Needs Input to Status.
  Workbench: add Proposal Version / Source Version numbers, Publication Key,
    Source Kind, Selected Action and Execution Error text properties.
  Knowledge / Ideas / Research Interests: add Archive Key when configured.
  Papers / Knowledge: add the Publication Key rich-text property for brief receipts.
  Papers: add Reading Summary and Interested; Notero: add Agent In Papers.
  Registered sources: add Agent Version, Agent Feedback, Agent History and Agent Processed.
  SimpRead: add Agent Archived. Research Interests: add Agent Pending.
  Existing additions are retained; successful writes are independently read back.

Scope and prerequisites:
  Configure the Notion token and data source IDs in YAML, and grant the integration
  access to those databases. Existing business fields such as Status and review
  decisions must be present. Setup adds assistant fields to existing databases.
  Existing properties and rows are preserved; no migration or new model job is requested.
  DBOS still starts and can recover previously unfinished workflows.

Examples:
  python -m assistant setup
  python -m assistant --config config.local.yaml setup

Run once on a new workspace or after required schema changes, not before every job.""",
    )
    options = parser.parse_args()
    return options
