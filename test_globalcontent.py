""" Pytest tests for the navigation stack in the globalcontent module """

from globalcontent import PageRouter, STACK_MAX_DEPTH


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


class TestPageRouterNavStack:
    """Tests for PageRouter navigation-stack behaviour."""

    def _make_router(self, on_nav_stack_changed=None):
        return PageRouter(
            content_panel=_MockPanel(),
            tab_height=64,
            context_buttons_panel=_MockPanel(),
            on_nav_stack_changed=on_nav_stack_changed,
        )

    def _register(self, router, label):
        page = _MockPage(label)
        router._pages_by_handle[label] = page
        return page

    # --- has_history ---

    def test_initial_no_history(self):
        router = self._make_router()
        assert not router.has_history

    def test_first_switch_no_history(self):
        router = self._make_router()
        page1 = self._register(router, 'a')
        router.switch_to_page(page1)
        assert not router.has_history

    def test_second_switch_creates_history(self):
        router = self._make_router()
        page1 = self._register(router, 'a')
        page2 = self._register(router, 'b')
        router.switch_to_page(page1)
        router.switch_to_page(page2)
        assert router.has_history

    # --- go_back ---

    def test_go_back_returns_to_previous_page(self):
        router = self._make_router()
        page1 = self._register(router, 'a')
        page2 = self._register(router, 'b')
        router.switch_to_page(page1)
        router.switch_to_page(page2)
        router.go_back()
        assert router.current_page is page1

    def test_go_back_exhausts_stack(self):
        router = self._make_router()
        page1 = self._register(router, 'a')
        page2 = self._register(router, 'b')
        router.switch_to_page(page1)
        router.switch_to_page(page2)
        router.go_back()
        assert not router.has_history

    def test_go_back_returns_false_when_empty(self):
        router = self._make_router()
        assert router.go_back() is False

    def test_go_back_does_not_push_to_stack(self):
        """Going back must not push the current page onto the stack."""
        router = self._make_router()
        page1 = self._register(router, 'a')
        page2 = self._register(router, 'b')
        router.switch_to_page(page1)
        router.switch_to_page(page2)
        router.go_back()
        # Stack is empty; a second go_back must fail
        assert router.go_back() is False

    def test_multiple_go_back_traverses_history(self):
        router = self._make_router()
        page1 = self._register(router, 'a')
        page2 = self._register(router, 'b')
        page3 = self._register(router, 'c')
        router.switch_to_page(page1)
        router.switch_to_page(page2)
        router.switch_to_page(page3)
        router.go_back()
        assert router.current_page is page2
        router.go_back()
        assert router.current_page is page1
        assert not router.has_history

    # --- stack depth limiting ---

    def test_stack_depth_is_limited(self):
        router = self._make_router()
        pages = [self._register(router, f'p{i}') for i in range(STACK_MAX_DEPTH + 2)]
        for page in pages:
            router.switch_to_page(page)
        assert len(router._history) == STACK_MAX_DEPTH

    def test_oldest_entry_dropped_when_depth_exceeded(self):
        """When the stack overflows, the oldest entry is dropped."""
        router = self._make_router()
        pages = [self._register(router, f'p{i}') for i in range(STACK_MAX_DEPTH + 2)]
        for page in pages:
            router.switch_to_page(page)
        # The oldest handle that survived is the one at index 1 (index 0 was dropped)
        assert router._history[0] == 'p1'

    # --- on_nav_stack_changed callback ---

    def test_callback_called_with_true_on_push(self):
        calls = []
        router = self._make_router(on_nav_stack_changed=calls.append)
        page1 = self._register(router, 'a')
        page2 = self._register(router, 'b')
        router.switch_to_page(page1)
        router.switch_to_page(page2)
        assert True in calls

    def test_callback_called_with_false_after_go_back_empties_stack(self):
        calls = []
        router = self._make_router(on_nav_stack_changed=calls.append)
        page1 = self._register(router, 'a')
        page2 = self._register(router, 'b')
        router.switch_to_page(page1)
        router.switch_to_page(page2)
        calls.clear()
        router.go_back()
        assert False in calls

    def test_no_callback_when_switching_same_page(self):
        calls = []
        router = self._make_router(on_nav_stack_changed=calls.append)
        page1 = self._register(router, 'a')
        router.switch_to_page(page1)
        calls.clear()
        router.switch_to_page(page1)
        assert calls == []
