"""Define command-line usage, workflow selection, and task-specific help."""

from pathlib import Path
import argparse
from uuid import UUID

JOB_HELP = {
    "brainstorm-material": {
        "help": "Explore research leads from a new paper, knowledge note or Idea log.",
        "description": "Connect one research note with relevant library history and public sources. "
                       "Save an exploration report and submit independent proposals to Workbench.",
        "epilog": "Example: python -m assistant run brainstorm-material",
    },
    "brainstorm-idea": {
        "help": "Explore an open question in an active research Idea.",
        "description": "Explore an active Idea with library history and web evidence. Read the report in the "
                       "command output or execution history. Review each proposed next step in Workbench.",
        "epilog": "Example: python -m assistant run brainstorm-idea",
    },
    "propose-tasks": {
        "help": "Propose work from Inbox, elevated TODOs and revised BrainStorm candidates.",
        "description": (
            "Read pending source versions through independent processors. Shared Organizer and\n"
            "Proposer submit outstanding work to Workbench. Reusable Inbox material is archived first."
        ),
        "epilog": """Sources:
  Inbox Status != Archived; TODO Status = elevated; Agent Processed unchecked.
  BrainStorm candidates reopened by Workbench feedback enter the same review cycle.
  Acknowledge the same source version when intake completes.
  Review and approve the proposal, then run process-workbench.

Example:
  python -m assistant run propose-tasks""",
    },
    "organize-papers": {
        "help": "Archive pending Notero papers and propose follow-up work.",
        "description": (
            "Read raw Notero papers, organize their supplied evidence and propose reading work.\n"
            "Archive grounded briefs in Papers and submit outstanding work to Workbench."
        ),
        "epilog": """Sources and outputs:
  Agent Processed unchecked selects pending Notero inputs. --page checks one record.
  Publication retains Papers reading metadata and human notes. Agent In Papers is
  checked only after successful Papers publication. Attachments are not downloaded.

Example:
  python -m assistant run organize-papers --page NOTERO_PAGE_ID""",
    },
    "organize-articles": {
        "help": "Archive useful SimpRead clips and propose follow-up work.",
        "description": (
            "SimpRead Processor reads clips and user notes. Shared Organizer identifies useful\n"
            "material for Papers or Knowledge and sends follow-up work to Proposer."
        ),
        "epilog": """Sources and outputs:
  Read Agent Archived unchecked and Agent Processed unchecked.
  Acknowledge after archiving and any follow-up proposal.
  A source can lead to multiple accepted Knowledge, Papers, Ideas or Interests outputs.
  Reconciled feedback reopens the same source with a new version.

Example:
  python -m assistant run organize-articles""",
    },
    "process-signals": {
        "help": "Propose work from explicit paper/feed follow-ups and pending interest requests.",
        "description": (
            "Read Papers/Research Feed with Follow Up checked, and research interests marked\n"
            "Agent Pending through source-specific processors and the shared proposal path."
        ),
        "epilog": """No Inbox copies are created. Interested marks tune the newspaper without proposals.
Follow Up is consumed after proposal publication; checking it again requests a new version.

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
  Open / Approved retention: Curator and Publisher store the reviewed Spark or Idea.
  Open / Submit External Result: receive the External report for a report-capable action and await result review.
  Open / Approved execution: use the saved workflow; result becomes Executed / Pending.
  plan / Executed / Qualified: finish planning and propose execution for fresh approval.
  Executed / Qualified: retain useful outputs, then Archived; otherwise Finished.
  Revision Requested / Unqualified: reopen source, never directly redo a worker.
  Rejected: Deprecated. Pending approvals and acceptance remain waiting.

Outputs:
  Papers, Knowledge, Ideas and Research Interests share the acceptance boundary.
  Explicit Follow Up requests belong to process-signals; Interested is preference feedback.

Example:
  python -m assistant run process-workbench""",
    },
    "recommend-papers": {
        "help": "Refresh Discovery Pool and publish a small research newspaper edition.",
        "description": (
            "Read newspaper topics, refresh discoveries, shortlist cached candidates and evaluate\n"
            "relevance. Recommendations publish directly to Research Feed, outside Workbench."
        ),
        "epilog": """Scope:
  Discovery Pool targets 100 recent finds; Research Feed selects five by default.
  Sources include papers, findings, methods, tools and datasets.
  Exploration targets 40/30/20/10 across core/broader/neighboring/cross-disciplinary.
  Daily recommendation maxima are caps, not quotas. Mainline Deep Read requires
  complete primary text. Missing evidence is reported, not fabricated.
  With discovery/evidence: codex, search and read public primary sources using
  the logged-in Codex CLI; recommender: local assesses evidence before publication.
  Configure codex.discovery_max_candidates and codex.discovery_recent_days to bound
  search. Selected excerpts do not qualify as Mainline Deep Read.
  With discovery/evidence: demo, use offline fixtures and never publish entries.
  Discovery Pool retains broad recent finds; the selected Research Feed edition
  defaults to five items. Optional likes personalize future editions automatically.
  Only an explicit Follow Up request enters process-signals and the proposal path.
  Normal runs select deep mode on runtime.recommendations.collector.deep_weekday
  (Monday=0, Sunday=6), otherwise light. Deep runs reuse a weekly Collector result.
  The daily edition is shared by both modes. No seven-day global discovery cutoff.
  Same-day retries reuse their durable report; new editions read current Notion recommendation directions.

Examples:
  python -m assistant run recommend-papers
  python -m assistant run process-signals""",
    },
}


for mode in ("deep", "light"):
    JOB_HELP[f"recommend-papers-{mode}"] = {
        "help": f"Collect research in {mode} mode, then publish today's edition.",
        "description": (
            "Deep: weekly Codex acquisition with web/OpenReview tools and reusable queries.\n"
            "Light: local OpenReview queries using weekly directions and coverage gaps.\n"
            "Both modes await acquisition before the same quality-gated daily edition."
        ),
        "epilog": """Cadence and durability:
  Deep collection is checkpointed once per ISO week; light collection once per day.
  Both modes share the daily edition identity. Repeated submissions reuse progress.
  Distribution targets combine breadth and paper age over the last 90 days.
  Source failures are reported; existing Pool candidates remain eligible.
  Local collection calls no model; subsequent non-OpenReview reading may still use Codex.

Examples:
  python -m assistant run recommend-papers-deep
  python -m assistant run recommend-papers-light

Start serve with the same configuration before submitting a job.""",
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
  Start serve in one terminal; run/status/resume contact its loopback HTTP service.
  Only serve launches DBOS and recovers unfinished work. Accepted jobs continue
  after a client disconnects. Stop serve before setup, which initializes schema
  without launching DBOS. Help and client commands never start an executor.

Logging:
  Log levels select which records are emitted; -v does not change those levels.
  Add -v or --verbose before or after the command/job for diagnostic fields,
  token usage details, and full exception tracebacks on emitted records.
  JSON business results on stdout are unchanged.

Examples:
  python -m assistant serve
  python -m assistant run propose-tasks
  python -m assistant run process-workbench -v
  python -m assistant run organize-papers --help
  python -m assistant --config config.local.yaml run process-workbench

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
        "run", help="Submit one job to serve and wait for its result, or detach.",
        formatter_class=formatter, parents=[verbose_options],
        description=(
            "Submit one named workflow pass to the running local service.\n"
            "The job may call models and update Notion; human approval boundaries remain."
        ),
        epilog="""Options and configuration:
  Select a job below; run JOB --help describes its sources, writes, and examples.
  --page PAGE_ID selects a source for paper/article intake or a BrainStorm starting point.
  Configure providers, model settings, and batch limits in YAML, not as CLI overrides.
  Start serve with the same --config first. --detach returns a durable workflow ID.
  Ctrl+C stops client waiting; accepted work keeps running in serve.
  Retry an uncertain submission using the printed --request-id; this reuses the
  original request. A new request ID creates a new dispatch.

Examples:
  python -m assistant run propose-tasks
  python -m assistant run process-workbench
  python -m assistant run organize-papers --page NOTERO_PAGE_ID
  python -m assistant run recommend-papers --help

Use serve for recurring schedules, or resume WORKFLOW_ID to recover a failed run.""",
    )
    submission_options = argparse.ArgumentParser(add_help=False)
    submission_options.add_argument("--detach", action="store_true", default=argparse.SUPPRESS,
                                    help="Return the workflow ID after durable submission; do not wait.")
    submission_options.add_argument("--request-id", type=UUID, metavar="UUID", default=argparse.SUPPRESS,
                                    help="Reuse the printed request UUID to retry submission without duplicating work.")
    run.add_argument("--detach", action="store_true", help="Submit and return the workflow ID without waiting.")
    run.add_argument("--request-id", type=UUID, metavar="UUID", help="Reuse a prior request UUID for safe resubmission.")
    run.set_defaults(page=None)
    jobs = run.add_subparsers(dest="job", required=True, title="jobs", metavar="JOB")
    for name, documentation in JOB_HELP.items():
        job = jobs.add_parser(name, formatter_class=formatter, parents=[verbose_options, submission_options], **documentation)
        if name in {"brainstorm-material", "brainstorm-idea"}:
            job.add_argument("--refresh", action="store_true", help="Explore the specified --page again with current evidence. Reuse --request-id when retrying the same round.")
            job.add_argument("--page", metavar="PAGE_ID", help="Explore this Notion page. "
                             "By default the research library selects an eligible starting point.")
        if name in {"organize-papers", "organize-articles"}:
            job.add_argument(
                "--page", metavar="PAGE_ID",
                help=(
                    "Check one raw Notion page ID instead of the next batch "
                    "(default: pending-input batch). Unchanged content remains deduplicated."
                ),
            )

    commands.add_parser(
        "serve", help="Serve local task requests, execute queues, and trigger configured schedules.",
        formatter_class=formatter, parents=[verbose_options],
        description=(
            "Start the local HTTP service and the sole DBOS executor.\n"
            "Accept manual jobs and trigger jobs listed in runtime.schedules using the\n"
            "same workflows and human-review boundaries as a manual run."
        ),
        epilog="""Schedule configuration:
  runtime:
    schedules:
      propose-tasks: "0 0 7 * * *"
      process-workbench: "0 */15 * * * *"
      recommend-papers-deep: "0 0 7 * * 0"
      recommend-papers-light: "0 0 7 * * 1-6"

  Use six cron fields: second minute hour day-of-month month day-of-week.
  Timezone: Asia/Shanghai. The example proposes tasks at 07:00 and processes reviews every
  15 minutes. With schedules: {} (default), the service still accepts manual jobs.
  Available jobs: propose-tasks, process-workbench, organize-papers,
  organize-articles, process-signals, reconcile-feedback, recommend-papers,
  recommend-papers-deep, recommend-papers-light, brainstorm-material, brainstorm-idea.

Persistence and shutdown:
  Schedules persist in DBOS. This command updates configured schedules and removes
  assistant-* schedules removed from YAML. Missed offline runs are not backfilled.
  Already-started unfinished workflows may recover on launch.
  Press Ctrl+C to stop; shutdown allows active workflows up to 10 seconds to finish.
  run/status/resume work concurrently as HTTP clients. Only one serve may own a
  runtime directory. Stop it before setup. HTTP listens on 127.0.0.1:8765 by default;
  change runtime.service.port in the YAML used by both service and clients.

Browser panel:
  Open http://127.0.0.1:8765/ after starting the service (use your configured port).
  Browse saved runs, inputs/results and steps; resume, cancel or preview deletion.
  Create/edit/pause/delete schedules online; changes persist to the selected YAML.
  Schedule edits apply immediately without restarting. No frontend process is required.

Examples:
  python -m assistant serve
  python -m assistant --config config.local.yaml serve

Start serve under your IDE debugger, then submit run JOB from another terminal.""",
    )
    status = commands.add_parser(
        "status", help="Query the service, or inspect a workflow and its saved result.",
        formatter_class=formatter, parents=[verbose_options],
        description=(
            "Query the running local service without launching DBOS or recovering work.\n"
            "Without an ID, print schedules and recent workflows. With an ID, print saved\n"
            "execution metadata and steps; --result retrieves the saved business report."
        ),
        epilog="""Examples:
  python -m assistant status
  python -m assistant status --limit 50
  python -m assistant status WORKFLOW_ID
  python -m assistant status WORKFLOW_ID --result

Use the same --config as serve. The service must be running.
Inspecting status never submits or resumes a business task.""",
    )
    status.add_argument("workflow_id", nargs="?", metavar="WORKFLOW_ID", help="Inspect one saved workflow.")
    status.add_argument("--result", action="store_true", help="Return the saved result/error for WORKFLOW_ID.")
    status.add_argument("--limit", type=int, default=20, metavar="N", help="Recent workflow count, 1-200 (default: 20).")
    resume = commands.add_parser(
        "resume", help="Recover an existing workflow using its saved checkpoints.",
        formatter_class=formatter, parents=[verbose_options],
        description=(
            "Ask the running service to recover an existing workflow.\n"
            "For ERROR workflows, rewind from the failed step and retain earlier successful\n"
            "checkpoints; recover failed child workflows first when recorded. Other states\n"
            "use DBOS resume. Active/completed workflows are watched without restarting."
        ),
        epilog="""Requirements and effects:
  Start serve with the original runtime.directory and compatible provider configuration.
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
    resume.add_argument("--detach", action="store_true", help="Return a recovery receipt without waiting.")
    resume.add_argument("--request-id", type=UUID, metavar="UUID", help="Retry the same recovery submission UUID.")
    resume.add_argument(
        "workflow_id", metavar="WORKFLOW_ID",
        help="Exact existing workflow ID from status, in the configured DBOS database.",
    )
    setup = commands.add_parser(
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
  Discovery Pool: create under notion.assistant_page_id when no pool is configured.
  Papers / Research Feed: add Follow Up for explicit task requests.
  Add research directions as rows in Assistant → Recommendation Tags in Notion.
  A blank Priority on a manually created row counts as 1. Check Paused to suspend it.
  Existing properties and rows are preserved; no model job is requested.
  Stop serve before setup. Setup does not start DBOS or recover workflow tasks.

Examples:
  python -m assistant setup
  python -m assistant --config config.local.yaml setup
  python -m assistant setup --recommendation-topic "RL" --recommendation-topic "Control"

Run once on a new workspace or after required schema changes, not before every job.""",
    )
    setup.add_argument("--recommendation-topic", dest="recommendation_topics", action="append", metavar="TOPIC",
                       help="Add a missing direction directly to Notion Recommendation Tags. Repeat for multiple directions.")
    options = parser.parse_args()
    if options.command == "status" and options.result and not options.workflow_id:
        parser.error("status --result requires WORKFLOW_ID")
    return options
