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
