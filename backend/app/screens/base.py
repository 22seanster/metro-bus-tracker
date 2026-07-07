"""Screen contract. Adding a new screen (e.g. Spotify now-playing) means:
implement this protocol, then append an instance to the registry in app/main.py.
The frame protocol and firmware never change."""

from datetime import datetime
from typing import Protocol, runtime_checkable

from PIL import Image, ImageDraw


@runtime_checkable
class Screen(Protocol):
    name: str
    dwell_seconds: int

    def is_active(self, now: datetime) -> bool:
        """Whether this screen should appear in the rotation right now."""
        ...

    def render(self, img: Image.Image, draw: ImageDraw.ImageDraw, now: datetime) -> None:
        """Draw onto a 64x32 black RGB image."""
        ...
