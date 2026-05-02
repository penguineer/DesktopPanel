# Copilot Instructions — DesktopPanel

DesktopPanel is a Python/Kivy application that runs on a Raspberry Pi touchscreen display.
It integrates with MQTT (sensor data) and AMQP/RabbitMQ (command dispatch).

---

## Language & Runtime

- Python **3.9**
- [Kivy](https://kivy.org/) 2.1 as the UI framework
- Deployed as a Docker container on a Raspberry Pi (ARM)

---

## Project Layout

The project is **flat** — all Python source modules live in the root directory alongside
`requirements.txt` and `Dockerfile`. There are no sub-packages.

| Path | Purpose |
|------|---------|
| `app.py` | Entry point; wires pages, MQTT, AMQP |
| `globalcontent.py` | `GlobalContentArea` base window; `ContentPage` page base class |
| `page_*.py` | One file per page tab |
| `statusbar.py` | Status bar, tray bar, tray icon widgets |
| `amqp.py` | AMQP/RabbitMQ connector and command dispatch |
| `mqtt.py` | MQTT client widget |
| `reloadable_json.py` | File-watching JSON loader |
| `test_*.py` | pytest test files |
| `assets/` | PNG icons and TTF fonts |

---

## Module Structure

Every module follows this layout:

```python
""" Module for <description> """ 

# --- stdlib imports ---
# --- third-party imports (kivy first, then others) ---
# --- local module imports ---

Builder.load_string("""               # KV language definition for the first widget
<WidgetClass>:
    ...
""")

class WidgetClass(...):               # Python class immediately follows its KV block
    ...
```

---

## Kivy UI (KV Language)

- UI for each widget is defined **inline** using `Builder.load_string()` placed
  **directly above** the corresponding Python class.
- Use `#:import SymbolName module.SymbolName` inside KV strings to bring Python
  identifiers into KV scope rather than importing them at module level.
- KV property bindings use conditional expressions for state-driven display:
  ```kv
  color: Colors.COLOR_RED if root.value_error else \
         Colors.COLOR_GREY if root.power is None else \
         Colors.COLOR_WHITE
  ```
- Multi-line KV values use `\` continuation with consistent indentation.

---

## Class Design

### Kivy Widgets

- Extend an appropriate Kivy layout class (`RelativeLayout`, `BoxLayout`,
  `AnchorLayout`, etc.) or a project base class (`ContentPage`, `TrayIcon`).
- Declare all reactive state as **Kivy properties** at class level:
  ```python
  conf   = DictProperty(None)
  mqttc  = ObjectProperty(None)
  status = StringProperty(None, allownone=True)
  ```
- Bind property observers in `__init__` with `self.bind(prop=self._on_prop)`.
- Name property observer methods `_on_<property>` for bindings set up via
  `self.bind(...)`, and `on_<property>` when overriding Kivy's automatic
  `on_<prop>` callback dispatch.
- Call `super().__init__(**kwargs)` (or `super(BaseClass, self).__init__(**kwargs)` 
  for older style) as the **last** call in `__init__`, after setting initial
  instance attributes and bindings.

### Non-Kivy Classes

- Use `object` as the explicit base class.
- Expose read-only fields via `@property`; keep the backing attribute private with
  a leading underscore.
- Use `@staticmethod` factory methods named `from_json_cfg(config)` to construct
  objects from a parsed JSON dict.

### Configuration Pattern

Every configurable class accepts a JSON-derived `dict` and follows this guard pattern:

```python
@staticmethod
def from_json_cfg(config: Optional[dict]):
    if config is None:
        return None
    cfg = config.get("section_key", None)
    if cfg is None:
        return None
    # validate required fields
    if not cfg.get("required_field"):
        raise ValueError("Required field must be provided!")
    return MyClass(...)
```

- Missing **required** config → `raise ValueError("... must be provided!")`
- Missing **optional** config → use a sensible default via `.get("key", DEFAULT)`

---

## Naming Conventions

| Entity | Convention | Example |
|--------|-----------|---------|
| Modules | `snake_case` | `reloadable_json.py` |
| Classes | `PascalCase` | `AmqpAccessConfiguration` |
| Public methods / functions | `snake_case` | `dispatch_command` |
| Private methods / attributes | `_snake_case` | `_on_conf`, `_observer` |
| Constants / palette entries | `UPPER_SNAKE_CASE` | `COLOR_GREEN` |
| Kivy property callbacks | `_on_<prop>` or `on_<prop>` | `_on_conf`, `on_temperature` |
| Unused callback parameters | leading `_` | `_instance`, `_client`, `_userdata` |

---

## Color Palette

Colors are expressed as `[r/256, g/256, b/256, alpha]` float lists.
The same semantic palette is used throughout the project:

| Name | RGBA source | Meaning |
|------|-------------|---------|
| Black | `[0, 0, 0, 1]` | Backgrounds |
| Grey | `[77/256, 77/256, 76/256, 1]` | Inactive / unknown |
| Green | `[0/256, 163/256, 86/256, 1]` | Connected / OK |
| Yellow | `[249/256, 176/256, 0/256, 1]` | Warning / active accent |
| Red | `[228/256, 5/256, 41/256, 1]` | Error / alarm / disconnected |
| Blue | `[0/256, 132/256, 176/256, 1]` | Info |

When a module uses colors extensively, define them in a local `Colors` class:

```python
class Colors:
    COLOR_GREY   = [77/256, 77/256, 76/256, 1]
    COLOR_GREEN  = [0/256, 163/256, 86/256, 1]
    COLOR_YELLOW = [249/256, 176/256, 0/256, 1]
    COLOR_RED    = [228/256, 5/256, 41/256, 1]
```

---

## MQTT Integration

- Widgets that consume MQTT data declare `mqttc = ObjectProperty(None)` and
  `conf = DictProperty(None)`.
- Override `on_conf` and `on_mqttc` (Kivy automatic callbacks) and delegate both
  to a shared `_update_mqtt()` helper:
  ```python
  def on_conf(self, _instance, _conf):
      self._update_mqtt()

  def on_mqttc(self, _instance, _mqttc):
      self._update_mqtt()

  def _update_mqtt(self):
      if not self.conf or not self.mqttc:
          return
      topic = self.conf.get("topic", None)
      self.mqttc.subscribe(topic, self._mqtt_callback)
  ```
- MQTT callbacks arrive on a background thread; schedule UI updates via
  `Clock.schedule_once(lambda dt: self._update_ui(payload))`.

---

## Deferred UI Updates

Always use `Clock.schedule_once(lambda dt: ...)` when updating Kivy widget state
from outside the main thread (MQTT callbacks, file-system events, async callbacks):

```python
Clock.schedule_once(lambda dt: self.setter('conf')(self, conf))
Clock.schedule_once(lambda dt: self.ids.rv.refresh_from_data())
```

---

## Lifecycle: Setup / Teardown

Objects that hold external resources (file observers, network connections) implement
paired `setup()` / `teardown()` methods:

```python
def setup(self):
    self._observer = Observer()
    self._observer.start()

def teardown(self):
    if self._observer is not None and self._observer.is_alive():
        self._observer.stop()
        self._observer.join()
```

Call `teardown()` in `__del__` and in `App.on_stop()`.

---

## Logging

Use the Kivy `Logger` (not `print` or the stdlib `logging` module):

```python
from kivy import Logger

Logger.info("TAG: message with %s placeholder", value)
Logger.warning("TAG: something unexpected happened: %s", reason)
Logger.error("TAG: something went wrong: %s", e)
```

Tag format: `"MODULENAME: "` — use a short, all-caps or PascalCase tag matching
the subsystem (e.g. `"AMQP: "`, `"MQTT: "`, `"Issues: "`).

---

## Error Handling

- Catch specific exceptions; never bare `except:`.
- Re-raise or log; don't silently swallow errors.
- JSON parsing errors: catch `json.decoder.JSONDecodeError`.
- Network errors: catch `ConnectionRefusedError`, `socket.gaierror`.
- Schedule reconnect attempts with `asyncio.get_running_loop().call_later(5, self._reconnect)`.

---

## Testing

- Test framework: **pytest** (`pytest --verbose`).
- Test files: `test_<module>.py` in the project root.
- Test classes: `class TestSubject:` (no base class).
- Assertions: plain `assert` statements.
- Expected exceptions: `pytest.raises(ExceptionType)`.
- Module docstring: `""" Pytest tests for the <module> module """`.

Example structure:
```python
""" Pytest tests for the foo module """

import pytest
from foo import FooClass

class TestFooClass:
    def test_no_config(self):
        assert FooClass.from_json_cfg(None) is None

    def test_missing_required(self):
        with pytest.raises(ValueError) as e:
            FooClass.from_json_cfg({"foo": {}})
        assert "must be provided" in str(e.value)
```

---

## Import Order

Follow PEP 8 import ordering within each file:

1. Standard library (`json`, `asyncio`, `socket`, …)
2. Third-party: Kivy imports first, then others (`pika`, `paho`, …)
3. Local modules

Group each section with a blank line between them.

---

## Kivy GL Stencil Rendering Constraint

**Background:** Every `ScrollView` and `RecycleView` is a `StencilView` internally.
`StencilView` uses OpenGL stencil buffer operations (push, use, unuse, pop) to clip
its content.  These operations leave the GL pipeline in a state where any
**texture-based rendering** — `Label` glyphs and `Image` textures — that was issued
**before** the stencil cycle in the same frame is **invisible** on screen.
Geometry-only instructions (`Line`, `Rectangle`, `Ellipse`, `RoundedRectangle`)
are unaffected and always draw correctly.

This is the root cause of the recurring "Presence Dialog invisible on System/GTD
pages" bugs: those pages contain `RecycleView`/`ScrollView` widgets that are still
on-screen when the dialog opens.  The HOME page has no scroll views, so the dialog
always appeared correctly there.

**Rules for placing UI elements:**

1. **Texture-based widgets (Label, Image, AsyncImage) that must be visible must
   render *after* any StencilView sibling in the same widget tree.**
   In Kivy, the last item in a layout's `children` list renders on top / last.
   `add_widget()` with the default `index=0` inserts at `children[0]` (last
   rendered). Widgets added by KV rules render in KV source order, which becomes
   the *reverse* of `children` order.

2. **Frame decorations, titles, and overlay elements in `FullscreenTimedModal`
   subclasses are re-ordered in `on_kv_post()`** (see `dlg.py`).  The title and
   close-button `AnchorLayout` containers carry the ids `title_anchor` and
   `close_btn_anchor` precisely so that `on_kv_post` can remove and re-insert them
   at the top of the stack *after* the dialog's content children (which may include
   `ScrollView`/`RecycleView`).  **Do not change the ids or remove the `on_kv_post`
   call without understanding this constraint.**

3. **Scroll-indicator arrows in `ScrollableList`** are raised to the top of the
   children stack by `_raise_arrows()`, which is called automatically from
   `bind_scroll_view()`.  This ensures the `▲`/`▼` `Label` widgets render after
   the wrapped `ScrollView`/`RecycleView`.  Any new overlay widget added on top of
   a `ScrollableList` must also be re-ordered after `bind_scroll_view()` is called.

4. **When adding a new overlay widget** (e.g. a status badge, tooltip, or floating
   button) on top of a container that includes a `ScrollView` or `RecycleView`,
   always insert the overlay widget *after* the scroll view in the render order.
   The safe pattern is:

   ```python
   def on_kv_post(self, base_widget):
       overlay = self.ids.my_overlay
       self.remove_widget(overlay)
       self.add_widget(overlay)  # re-inserts at children[0] = rendered last = on top
   ```

5. **`canvas.after` is reliable.** Pure-geometry decorations (border lines, divider
   lines) drawn in `canvas.after` always execute after all children finish
   rendering — including all stencil push/pop cycles — so they are safe to use
   unconditionally for frame borders and similar decorations (see `dlg.py`).

---

## Pages

New pages follow this minimal pattern:

```python
""" Module for page <Name> """

from kivy.lang import Builder
import globalcontent

Builder.load_string("""
<MyPage>:
    label: 'mypage'
    icon: 'assets/icon_mypage.png'

    # KV layout here
""")

class MyPage(globalcontent.ContentPage):
    pass
```

Register the page in `app.py` inside `build()` using `Clock.schedule_once` and
supply a `conf_lambda` if the page needs a section of the global config:

```python
my_page = MyPage()
my_page.conf_lambda = lambda conf: conf.get("mypage", dict())
Clock.schedule_once(lambda dt: ca.register_content(my_page))
```
