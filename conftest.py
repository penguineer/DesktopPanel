"""
Pytest configuration for the DesktopPanel test suite.

Sets KIVY_WINDOW=headless before any test module is imported so that Kivy
does not attempt to open an X11 or SDL2 window during test collection.
"""

import os

os.environ.setdefault('KIVY_WINDOW', 'headless')
