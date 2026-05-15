"""Hypothesis settings for property-based tests.

Sets deadline=None globally to avoid flaky DeadlineExceeded failures on
Windows where file I/O and process startup are slower than the default 200ms.
"""
from hypothesis import settings

settings.register_profile("ci", deadline=None)
settings.load_profile("ci")
