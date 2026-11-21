# Coverage-driven research collection

The newspaper collects before editing. Collector reads interests, publication coverage,
current Pool stock and reusable queries, calls source tools, and returns discoveries.
Recommender then ranks, reads, assesses and publishes qualified selections. Workbench
approval remains separate from this autonomous newspaper.

See the [business information-flow diagram](../information-flow.drawio),
[newspaper sequence](newspaper-sequence.md), and [local service sequence](service-sequences.md).

## Run on the dedicated local host

```bash
uv sync
uv run python -m assistant serve
```

Use another terminal with the same configuration:

```bash
uv run python -m assistant run recommend-papers-deep --detach
uv run python -m assistant run recommend-papers-light --detach
uv run python -m assistant status
uv run python -m assistant status WORKFLOW_ID --result
```

Normal `recommend-papers` chooses deep on the configured deep_weekday (Monday=0,
Sunday=6), otherwise light. Explicit deep/light commands select the mode directly.

The local configuration and example define two Shanghai-time schedules:

```yaml
runtime:
  schedules:
    recommend-papers-deep: "0 0 7 * * 0"
    recommend-papers-light: "0 0 7 * * 1-6"
```

They enqueue the same serial business dispatch, with different collection modes.
Sunday runs deep acquisition; Monday-Saturday run local acquisition. Both workflows
await collection before selecting the day's newspaper. There is no timing race between
an independently scheduled collection and publication command.

Serve remains foreground for IDE debugging. The optional systemd user service can
supervise it without changing workflow code; see [local operation](local-service.md).
The implementation does not install/start a host service automatically.

## Collector modes and costs

**Deep** delegates one research session to the existing logged-in Codex CLI. It receives
bounded interest/Pool context and the coverage table, adapts public web queries, and can
call a read-only OpenReview MCP server. It returns candidates, retrieval limitations
and concrete English queries that the local collector can reuse. Source-tool calls and
pagination have enforced limits. Native Codex web search is bounded by the session
expiration and the prompt's budget; its exact number of web calls is not a hard host
counter. Runtime telemetry records actual tool activity and usage.

**Light** does not call Codex or another model for acquisition. It prioritizes the saved
weekly queries using current coverage gaps and stock, then calls OpenReview directly.
When a weekly plan is unavailable, topic-based bootstrap queries are used and identified
in their reason. This is a cheap source refresh, not a second autonomous research agent.

A successful deep batch is checkpointed by ISO week, and a light batch by day. Weekly
identity does not vary with a changed preference or prompt, so repeated submissions
cannot silently buy a second successful weekly scan. Failed invocations can consume
quota; an explicit retry of failed work may call Codex again. Change code/config only
with the normal version/recovery checks in mind.

Both modes share the daily edition identity, including its editorial policy/topic
fingerprint. Running light and deep on one day can collect both, but reuses an already
completed edition rather than publishing twice. Collection failures are visible in the
report and do not prevent selecting from existing usable Pool stock.

Collector cost and reading cost are independent. OpenReview candidates use a direct API
abstract/discussion reader. Other candidates still use the configured evidence reader;
with `providers.evidence: codex`, daily editorial reading can still consume Codex quota.
Chinese Pool display preparation and local ranking/assessment also retain their
configured model usage. Original paper titles are preserved separately from display translations.

## Breadth-by-age coverage

The default breadth weights remain Core 40%, Broader 30%, Neighboring 20% and
Cross-disciplinary 10%. Publication ages are disjoint calendar intervals:

| Age | Weight |
| --- | --- |
| 0-7 days inclusive | 5% |
| More than 7 days, up to 1 calendar month | 15% |
| More than 1 month, up to 3 months | 20% |
| More than 3 months, up to 6 months | 15% |
| More than 6 months, up to 1 year | 15% |
| More than 1 year, up to 3 years | 15% |
| More than 3 years | 15% |

The target of a cell is the product of normalized breadth and age weights. Confirmed
publications from the last 90 days determine actual coverage. Age is recorded at the
recommendation date and never reclassified simply because time passes. Unknown/future
publication dates remain outside this table. Old existing editions lack these new age
snapshots, so the table warms up from newly confirmed publications rather than inventing
historical ages. Retrying publication does not count twice.

Collector priorities subtract available stock from coverage deficits; weekly model
context contains a bounded stock sample plus counts for the full Pool. Editorial
reading interleaves ranked candidates across the table. Quality assessment still gates
publication, and fewer than five recommendations, including zero, remains valid. There
is no seven-day global cutoff. Frontier Radar has its own configurable 90-day window;
older useful work can appear in other editorial categories.

Relevant settings:

```yaml
runtime:
  recommendations:
    coverage_days: 90
    ages:
      week: 0.05
      month: 0.15
      quarter: 0.20
      half_year: 0.15
      year: 0.15
      three_years: 0.15
      older: 0.15
    collector:
      deep_provider: codex
      light_provider: local
      deep_weekday: 6
      max_queries: 6
      max_candidates: 40
      context_pool_size: 30
      frontier_days: 90
```

Weekly directions live in `runtime.directory/v2/collector-directions.json`; complete
acquisition inputs/results and tool telemetry are retained by DBOS. Daily reports keep
candidate evidence, raw public review notes, reviewer/author attribution and limitations.

## OpenReview scope and account setup

The adapter uses API v2 public search and forum notes. A small anonymous public-search
request succeeded during implementation; the subsequent anonymous forum-detail request
returned HTTP 403. Configure an OpenReview account in the environment of the process
running serve to validate public review retrieval on your host:

```bash
export OPENREVIEW_USERNAME='your-account-email'
read -rsp 'OpenReview password: ' OPENREVIEW_PASSWORD
export OPENREVIEW_PASSWORD
```

Under systemd, use the optional private environment file described in the local service
guide. Credentials are read by the API tool and never passed to the model as prompt
content. Only notes explicitly readable by `everyone` are returned, even when an
account can access private reviews. No private reviewer-assignment content is collected.

Optional source settings:

```yaml
openreview:
  venues: []
  page_size: 50
  max_pages: 3
  max_discussions: 40
  timeout_seconds: 30
  interval_seconds: 1
  username_env: OPENREVIEW_USERNAME
  password_env: OPENREVIEW_PASSWORD
```

Use exact verified venue IDs to restrict conferences; an empty list searches public
matching results across venues. API search uses `term`, not a fabricated `query` field.
Publication-date filtering is applied to bounded search results locally; sparse results
or exhausted pages are reported as limited coverage. This source is not a claim of
complete historical conference indexing. Weekly public-web exploration supplements
historical and cross-disciplinary work that OpenReview cannot supply.

For shortlisted OpenReview papers, the reader uses API v2 and falls back to API v1
when a historical forum is absent from v2 (not when access is denied). It retrieves the original abstract and
public thread, retaining note IDs, roles, reply links, timestamps and raw rating scales.
Official reviews, meta reviews, decisions, author responses and public comments are
separated. Discussion truncation is explicit. API abstract/thread access does not mean
the PDF has been read; full_text remains false. Scores across different conferences
are not averaged, and acceptance does not certify scientific correctness.

The Feed adds reviewer assessment, author responses, unresolved issues and source links.
Pool Candidate Data preserves discovery provenance and the forum identity. The same
paper's OpenReview forum/PDF/comment URLs deduplicate to one forum identity; DOI takes
precedence when known. Cross-platform versions without a shared identifier are not
silently merged by approximate title alone.

No new Notion columns are required. Existing Candidate Data and Feed report bodies
carry the added metadata. Existing human feedback and selected flags are preserved.

### Recommendation Tags

Run `uv run python -m assistant setup` with the service stopped. Setup creates
Recommendation Tags under Assistant, seeds missing initial topics, and adds a
relation of that name to Discovery Pool, Research Feed and Papers. Existing
Topics, Keywords and legacy multi-select Tags retain their values. Existing
records can be linked directly in Notion. New discoveries and paper briefs are
classified against the catalog during preparation. Accepted Feed papers carry
their source relations into Papers.

Each catalog row has a Name, Definition, Aliases, Priority, Feedback Weight and
Paused checkbox. Seed directions start at priority 1. Newly discovered directions
start at 0. Set Priority to steer searches explicitly. Liking a linked publication
adds one point per direction, up to four, across the three collections using its
publication identity. Preference reads recompute Feedback Weight, including when
likes are removed. Paused directions remain available for classification. Directions with a positive combined weight
guide discovery and ranking within the existing
breadth-by-age coverage policy. Unlinked historical papers can still be read and
ranked from their metadata; link them to include their likes in tag weights.
