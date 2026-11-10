"""Tests for GTD issue-list observer cleanup."""

from types import SimpleNamespace
from unittest.mock import Mock

from issues import IssueList
from page_gtd import GtdPage


def test_issue_list_teardown_stops_observer():
    observer = Mock()
    state = SimpleNamespace(_observer=observer)

    IssueList.teardown(state)
    IssueList.teardown(state)

    observer.teardown.assert_called_once_with()
    assert state._observer is None


def test_gtd_page_tears_down_issue_list():
    issue_list = Mock()
    page = SimpleNamespace(ids=SimpleNamespace(issuelist=issue_list))

    GtdPage.teardown(page)

    issue_list.teardown.assert_called_once_with()
