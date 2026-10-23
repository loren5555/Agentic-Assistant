"""Discover and assess new research material before recommending it.

Responsibility:
    Separate candidate discovery, primary-evidence retrieval, relevance/quality
    assessment, and Research Feed storage into replaceable capabilities.

Inputs:
    Human-maintained ResearchInterest entries, discovered PaperCandidate metadata,
    actual PaperEvidence, and recommendation publication identities.

Outputs:
    Candidate lists, retrieved evidence, RecommendationAssessment decisions,
    published recommendation URLs, and Interested feedback follow-ups to Inbox.
    RecommendationRun records selections, rejections, failures, and real writes.

Participants:
    Discovery service, evidence reader, assessment agent, feed storage plugin,
    recommend_papers task, process_reviews follow-ups, and human readers.

Boundaries:
    The workflow enforces evidence gates, duplicates, and daily maxima; zero
    publication is valid. Long-term interests and Human Feedback are human-owned.
    Mainline Deep Read requires full text. Interested creates an Inbox follow-up,
    never a direct Papers write. Current demo discovery cannot publish real entries.
"""
