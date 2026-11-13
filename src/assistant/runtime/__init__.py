"""Compose and host the assistant's local durable execution environment.

Input origin: YAML settings, local HTTP clients and persisted schedule triggers.
Output destination: DBOS state, provider-backed business outputs and JSON reports.
Application registers task instances before serve launches recovery. Service
modules separate client submission/inspection from execution; index, serialization
and recovery retain the existing persistence and code-version boundaries.
"""
