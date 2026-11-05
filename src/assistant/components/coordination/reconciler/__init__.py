"""Translate human decisions into source updates, never direct worker retries.

Input origin:
    Workbench clarification answers, revisions/rejections, unqualified results
    and original source snapshots.
Output destination:
    Feedback is appended on the original source as a new pending version. Old
    work becomes Superseded or Deprecated; the normal intake creates fresh proposals.
Responsibility:
    Return submitted answers and earlier questions to the source. Interpret
    lifecycle decisions mechanically, preserve history, and expose a
    stable feedback identity so a retry cannot create another source version.
"""
