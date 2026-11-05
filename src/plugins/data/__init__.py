"""Implement data capabilities.

Input origin:
    The corresponding assistant component contracts and workflow calls.
Output destination:
    Role-specific results return to the caller; storage implementations perform
    the documented source/destination operations.
Responsibility:
    Group interchangeable implementations by role, then provider. Shared helpers
    retain common SDK mechanics without owning workflow progression.
"""
