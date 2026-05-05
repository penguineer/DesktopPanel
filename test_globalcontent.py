""" Pytest tests for the navigation stack in the globalcontent module """

from globalcontent import PageRouter, NavBackWidget


class _MockPage:
    """Minimal stand-in for a ContentPage used by PageRouter."""

    def __init__(self, label):
        self.label = label
        self.active = False


class _MockPanel:
    """Minimal stand-in for Kivy layout widgets used by PageRouter."""

    def add_widget(self, _w):
        pass

    def remove_widget(self, _w):
        pass


class _MockNavBack:
    """Minimal stand-in for NavBackWidget that allows testing the stack logic.

    Borrows the unbound methods from NavBackWidget and calls them with this
    plain object as ``self``, so no Kivy Window is required.
    """

    STACK_MAX_DEPTH = NavBackWidget.STACK_MAX_DEPTH

    def __init__(self):
        self._history = []
        self._going_back = False
        self._current_handle = None
        self._switch_callback = None
        self.has_history = False

    _on_page_selected = NavBackWidget._on_page_selected
    go_back = NavBackWidget.go_back


def _make_router():
    return PageRouter(
        content_panel=_MockPanel(),
        tab_height=64,
        context_buttons_panel=_MockPanel(),
    )


def _register(router, label):
    page = _MockPage(label)
    router._pages_by_handle[label] = page
    return page


class TestPageRouterEvent:
    """Tests for PageRouter.on_page_selected event dispatch."""

    def test_event_fires_on_first_navigation(self):
        router = _make_router()
        calls = []
        router.bind(on_page_selected=lambda _inst, h: calls.append(h))
        page = _register(router, 'a')
        router.switch_to_page(page)
        assert calls == ['a']

    def test_event_fires_on_different_page(self):
        router = _make_router()
        page1 = _register(router, 'a')
        page2 = _register(router, 'b')
        router.switch_to_page(page1)
        calls = []
        router.bind(on_page_selected=lambda _inst, h: calls.append(h))
        router.switch_to_page(page2)
        assert calls == ['b']

    def test_event_fires_even_for_same_page(self):
        """Re-selecting the current page must still dispatch on_page_selected."""
        router = _make_router()
        page = _register(router, 'a')
        router.switch_to_page(page)
        calls = []
        router.bind(on_page_selected=lambda _inst, h: calls.append(h))
        router.switch_to_page(page)
        assert calls == ['a']

    def test_event_not_fired_when_page_is_none(self):
        router = _make_router()
        calls = []
        router.bind(on_page_selected=lambda _inst, h: calls.append(h))
        router.switch_to_page(None)
        assert calls == []


class TestNavBackWidgetStack:
    """Tests for the navigation history stack managed by NavBackWidget."""

    def _make_wired(self):
        """Create a mock nav-back widget wired to a mock router."""
        router = _make_router()
        nav = _MockNavBack()
        router.bind(on_page_selected=nav._on_page_selected)
        nav._switch_callback = router.switch_to_label
        return router, nav

    # --- has_history ---

    def test_initial_no_history(self):
        _, nav = self._make_wired()
        assert not nav.has_history

    def test_first_navigation_no_history(self):
        router, nav = self._make_wired()
        page = _register(router, 'a')
        router.switch_to_page(page)
        assert not nav.has_history

    def test_second_navigation_creates_history(self):
        router, nav = self._make_wired()
        page1 = _register(router, 'a')
        page2 = _register(router, 'b')
        router.switch_to_page(page1)
        router.switch_to_page(page2)
        assert nav.has_history

    def test_same_page_does_not_push_history(self):
        router, nav = self._make_wired()
        page = _register(router, 'a')
        router.switch_to_page(page)
        router.switch_to_page(page)
        assert not nav.has_history

    # --- go_back ---

    def test_go_back_returns_to_previous_page(self):
        router, nav = self._make_wired()
        page1 = _register(router, 'a')
        page2 = _register(router, 'b')
        router.switch_to_page(page1)
        router.switch_to_page(page2)
        nav.go_back()
        assert router.current_page is page1

    def test_go_back_exhausts_stack(self):
        router, nav = self._make_wired()
        page1 = _register(router, 'a')
        page2 = _register(router, 'b')
        router.switch_to_page(page1)
        router.switch_to_page(page2)
        nav.go_back()
        assert not nav.has_history

    def test_go_back_returns_false_when_empty(self):
        _, nav = self._make_wired()
        assert nav.go_back() is False

    def test_go_back_does_not_push_to_stack(self):
        """Going back must not add the current page back to the stack."""
        router, nav = self._make_wired()
        page1 = _register(router, 'a')
        page2 = _register(router, 'b')
        router.switch_to_page(page1)
        router.switch_to_page(page2)
        nav.go_back()
        # Stack is empty; a second go_back must fail
        assert nav.go_back() is False

    def test_multiple_go_back_traverses_history(self):
        router, nav = self._make_wired()
        page1 = _register(router, 'a')
        page2 = _register(router, 'b')
        page3 = _register(router, 'c')
        router.switch_to_page(page1)
        router.switch_to_page(page2)
        router.switch_to_page(page3)
        nav.go_back()
        assert router.current_page is page2
        nav.go_back()
        assert router.current_page is page1
        assert not nav.has_history

    # --- stack depth limiting ---

    def test_stack_depth_is_limited(self):
        router, nav = self._make_wired()
        pages = [_register(router, f'p{i}') for i in range(_MockNavBack.STACK_MAX_DEPTH + 2)]
        for page in pages:
            router.switch_to_page(page)
        assert len(nav._history) == _MockNavBack.STACK_MAX_DEPTH

    def test_oldest_entry_dropped_when_depth_exceeded(self):
        """When the stack overflows, the oldest entry is dropped."""
        router, nav = self._make_wired()
        pages = [_register(router, f'p{i}') for i in range(_MockNavBack.STACK_MAX_DEPTH + 2)]
        for page in pages:
            router.switch_to_page(page)
        # Index 0 (the very first page) was dropped; index 1 is now the oldest
        assert nav._history[0] == 'p1'


class TestGoBackIfCurrent:
    """Tests for the go-back-if-current behaviour wired via _go_back_callback."""

    def _make_wired(self):
        """Create a mock nav-back widget fully wired to a mock router."""
        router = _make_router()
        nav = _MockNavBack()
        router.bind(on_page_selected=nav._on_page_selected)
        nav._switch_callback = router.switch_to_label
        router._go_back_callback = nav.go_back
        return router, nav

    def test_selecting_current_page_goes_back(self):
        """Re-selecting the active page navigates back when history is available."""
        router, nav = self._make_wired()
        page1 = _register(router, 'a')
        page2 = _register(router, 'b')
        router.switch_to_page(page1)
        router.switch_to_page(page2)
        router.switch_to_page(page2)
        assert router.current_page is page1

    def test_selecting_current_page_no_history_stays(self):
        """Re-selecting the active page with no history does not change the page."""
        router, nav = self._make_wired()
        page = _register(router, 'a')
        router.switch_to_page(page)
        router.switch_to_page(page)
        assert router.current_page is page

    def test_go_back_if_current_false_stays_on_page(self):
        """Passing go_back_if_current=False keeps the page open even if already active."""
        router, nav = self._make_wired()
        page1 = _register(router, 'a')
        page2 = _register(router, 'b')
        router.switch_to_page(page1)
        router.switch_to_page(page2)
        router.switch_to_page(page2, go_back_if_current=False)
        assert router.current_page is page2

    def test_go_back_if_current_false_still_dispatches_event(self):
        """go_back_if_current=False still fires on_page_selected for same page."""
        router, nav = self._make_wired()
        page = _register(router, 'a')
        router.switch_to_page(page)
        calls = []
        router.bind(on_page_selected=lambda _inst, h: calls.append(h))
        router.switch_to_page(page, go_back_if_current=False)
        assert calls == ['a']

    def test_selecting_current_page_by_label_goes_back(self):
        """switch_to_label also goes back when the target page is already active."""
        router, nav = self._make_wired()
        page1 = _register(router, 'a')
        page2 = _register(router, 'b')
        router.switch_to_page(page1)
        router.switch_to_page(page2)
        router.switch_to_label('b')
        assert router.current_page is page1

    def test_go_back_if_current_does_not_push_to_stack(self):
        """Going back via go_back_if_current must not push anything onto the stack."""
        router, nav = self._make_wired()
        page1 = _register(router, 'a')
        page2 = _register(router, 'b')
        router.switch_to_page(page1)
        router.switch_to_page(page2)
        router.switch_to_page(page2)  # triggers go_back
        assert router.current_page is page1
        assert not nav.has_history


class TestNoDuplicatesOnStack:
    """Tests for the no-consecutive-duplicates invariant on the history stack."""

    def _make_wired(self):
        router = _make_router()
        nav = _MockNavBack()
        router.bind(on_page_selected=nav._on_page_selected)
        nav._switch_callback = router.switch_to_label
        return router, nav

    def test_no_consecutive_duplicate_push(self):
        """If the top of the stack already holds the page being pushed, skip the push."""
        _, nav = self._make_wired()
        # Manually seed history with 'a' on top, then simulate a push of 'a' again.
        nav._current_handle = 'b'
        nav._history = ['a']
        # Calling _on_page_selected as if we navigated from 'b' to 'a' should NOT
        # push 'b' because… wait, this test exercises the guard for the case where
        # _history[-1] == _current_handle (both are 'a') when navigating away.
        nav._current_handle = 'a'
        nav._history = ['a']
        # Now navigate to 'b' — the top of stack is already 'a' == _current_handle,
        # so 'a' must NOT be pushed again.
        nav._on_page_selected(None, 'b')
        assert nav._history == ['a']

    def test_go_back_skips_current_page_entries(self):
        """go_back pops past entries that match the current page."""
        router, nav = self._make_wired()
        page1 = _register(router, 'a')
        page2 = _register(router, 'b')
        router.switch_to_page(page1)
        router.switch_to_page(page2)
        # Manually inject a duplicate of current page ('b') at the top of the stack.
        nav._history.append('b')
        # go_back should skip 'b' and land on 'a'.
        nav.go_back()
        assert router.current_page is page1

    def test_go_back_returns_false_when_only_duplicates(self):
        """go_back returns False if the stack contains only entries matching current."""
        _, nav = self._make_wired()
        nav._current_handle = 'a'
        nav._history = ['a', 'a', 'a']
        nav.has_history = True
        result = nav.go_back()
        assert result is False
        assert not nav.has_history

