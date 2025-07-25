"""windowcomponents.py"""

# ~ Type Checking (Pyright and MyPy) - Strict Mode
# ~ Linting - Ruff
# ~ Formatting - Black - max 110 characters / line

# Python imports
from __future__ import annotations
import time
from typing import Any, TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from textual.visual import VisualType
    from textual.app import ComposeResult
    from textual_window.window import Window

# Textual and Rich imports
import textual.events as events
from textual.widget import Widget
from textual import on, work
from textual.geometry import clamp
from textual.containers import Horizontal, Container
from textual.screen import ModalScreen
from textual.geometry import Offset

# Local imports
from textual_window.button_bases import ButtonStatic, NoSelectStatic
from textual_window.tiling import TilingLayout


BUTTON_SYMBOLS: dict[str, str] = {
    "close": "X",
    "maximize": "☐",
    "restore": "❐",
    "minimize": "—",
    "hamburger": "☰",
    "resizer": "◢",
    "tiling": "⊞",  # Tiling mode button
    "move_prev": "◀",  # Shift this window left
    "move_next": "▶",  # Shift this window right
    "rotate_left": "↺",  # Rotate entire list left
    "rotate_right": "↻",  # Rotate entire list right
    "toggle_floating": "⊡",  # Toggle this window's floating state
}


class HamburgerMenu(ModalScreen[None]):

    CSS = """
    HamburgerMenu {
        background: $background 0%;
        align: left top;    /* This will set the starting coordinates to (0, 0) */
    }                       /* Which we need for the absolute offset to work */
    #menu_container {
        background: $surface;
        width: 14; height: 2;
        border-left: wide $panel;
        border-right: wide $panel;        
        &.bottom { border-top: hkey $panel; }
        &.top { border-bottom: hkey $panel; }
        & > ButtonStatic {
            &:hover { background: $panel-lighten-2; }
            &.pressed { background: $primary; }        
        }
    }
    """

    def __init__(
        self,
        menu_offset: Offset,
        window: Window,
        options: dict[str, Callable[..., Optional[Any]]],
    ) -> None:

        super().__init__()
        self.menu_offset = menu_offset
        self.window = window
        self.options = options

    def compose(self) -> ComposeResult:

        with Container(id="menu_container"):
            for key in self.options.keys():
                yield ButtonStatic(key, name=key)

    def on_mount(self) -> None:

        menu = self.query_one("#menu_container")
        y_offset = self.menu_offset.y - 2 if self.menu_offset.y >= 2 else 0
        menu.offset = Offset(self.menu_offset.x - 9, y_offset)

    def on_mouse_up(self) -> None:

        self.dismiss(None)

    @on(ButtonStatic.Pressed)
    def button_pressed(self, event: ButtonStatic.Pressed) -> None:

        if event.button.name:
            self.call_after_refresh(self.options[event.button.name])


class CloseButton(NoSelectStatic):

    def __init__(self, content: VisualType, window: Window, **kwargs: Any):
        super().__init__(content=content, **kwargs)
        self.window = window
        self.click_started_on: bool = False  # see note below

        # You might think that using self.capture_mouse() here would be simpler than
        # using a flag. But it causes issues. capture_mouse really shines when it's
        # used on buttons that need to move around the screen. (And it is used for that
        # purpose below). But for this button and several others, they will never be moving
        # around while actively trying to click them. So using capture_mouse() causes various
        # small issues that are totally unnecessary. (inconsistent behavior, glitchiness, etc.)

    def on_mouse_down(self, event: events.MouseDown) -> None:

        if event.button == 1:  # left button
            self.click_started_on = True
            self.add_class("pressed")
            self.window.focus()

    def on_mouse_up(self) -> None:

        self.remove_class("pressed")
        if self.click_started_on:
            self.window.close_window()
            self.click_started_on = False

    def on_leave(self) -> None:

        self.remove_class("pressed")
        self.click_started_on = False


class HamburgerButton(NoSelectStatic):

    def __init__(
        self,
        content: VisualType,
        window: Window,
        options: dict[str, Callable[..., Optional[Any]]],
        **kwargs: Any,
    ):
        super().__init__(content=content, **kwargs)
        self.window = window
        self.options = options
        self.click_started_on: bool = False

    def on_mouse_down(self, event: events.MouseDown) -> None:

        if event.button == 1:  # left button
            self.click_started_on = True
            self.add_class("pressed")
            self.window.focus()

    async def on_mouse_up(self, event: events.MouseUp) -> None:

        self.remove_class("pressed")
        if self.click_started_on:
            self.show_popup(event)
            self.click_started_on = False

    def on_leave(self) -> None:

        self.remove_class("pressed")
        self.click_started_on = False

    @work
    async def show_popup(self, event: events.MouseUp) -> None:

        menu_offset = event.screen_offset

        await self.app.push_screen_wait(
            HamburgerMenu(
                menu_offset=menu_offset,
                window=self.window,
                options=self.options,
            )
        )


class MaximizeButton(NoSelectStatic):

    def __init__(self, content: VisualType, window: Window, **kwargs: Any):
        super().__init__(content=content, **kwargs)
        self.window = window
        self.click_started_on: bool = False
        self.tooltip = "Maximize" if self.window.maximize_state is False else "Restore"

    def on_mouse_down(self, event: events.MouseDown) -> None:

        if event.button == 1:  # left button
            self.click_started_on = True
            self.add_class("pressed")
            self.window.focus()

    def on_mouse_up(self) -> None:

        self.remove_class("pressed")
        if self.click_started_on:
            self.window.toggle_maximize()
            self.click_started_on = False

    def on_leave(self) -> None:

        self.remove_class("pressed")
        self.click_started_on = False

    def swap_in_restore_icon(self) -> None:

        self.update(BUTTON_SYMBOLS["restore"])
        self.tooltip = "Restore"

    def swap_in_maximize_icon(self) -> None:

        self.update(BUTTON_SYMBOLS["maximize"])
        self.tooltip = "Maximize"


class TilingButton(NoSelectStatic):
    """Button for cycling through tiling modes."""

    def __init__(self, content: VisualType, window: Window, **kwargs: Any):
        super().__init__(content=content, **kwargs)
        self.window = window
        self.click_started_on: bool = False
        self.tooltip = "Cycle Tiling Mode"

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button == 1:  # left button
            self.click_started_on = True
            self.add_class("pressed")
            self.window.focus()

    def on_mouse_up(self) -> None:
        self.remove_class("pressed")
        if self.click_started_on:
            self._cycle_tiling_mode()
            self.click_started_on = False

    def on_leave(self) -> None:
        self.remove_class("pressed")
        self.click_started_on = False

    def _cycle_tiling_mode(self) -> None:
        """Cycle through tiling modes."""
        from textual_window.manager import window_manager

        modes = [
            TilingLayout.FLOATING,
            TilingLayout.HORIZONTAL_SPLIT,
            TilingLayout.VERTICAL_SPLIT,
            TilingLayout.GRID,
            TilingLayout.MASTER_DETAIL,
        ]

        current_index = modes.index(window_manager.tiling_layout)
        next_index = (current_index + 1) % len(modes)
        new_mode = modes[next_index]
        window_manager.set_tiling_layout(new_mode)

        # Update button symbol and tooltip to show current mode
        mode_symbols = {
            TilingLayout.FLOATING: "⊞",  # Default tiling symbol
            TilingLayout.HORIZONTAL_SPLIT: "⊟",  # Horizontal split
            TilingLayout.VERTICAL_SPLIT: "⊞",  # Vertical split
            TilingLayout.GRID: "⊡",  # Grid layout
            TilingLayout.MASTER_DETAIL: "⊞",  # Master detail
        }

        mode_names = {
            TilingLayout.FLOATING: "Floating",
            TilingLayout.HORIZONTAL_SPLIT: "Horizontal Split",
            TilingLayout.VERTICAL_SPLIT: "Vertical Split",
            TilingLayout.GRID: "Grid Layout",
            TilingLayout.MASTER_DETAIL: "Master Detail",
        }

        self.update(mode_symbols[new_mode])
        self.tooltip = f"Tiling: {mode_names[new_mode]}"


class MovePrevButton(NoSelectStatic):
    """Button for moving window to previous position in tiling order."""

    def __init__(self, content: VisualType, window: Window, **kwargs: Any):
        super().__init__(content=content, **kwargs)
        self.window = window
        self.click_started_on: bool = False
        self.tooltip = "Shift This Window Left"

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button == 1:  # left button
            self.click_started_on = True
            self.add_class("pressed")
            self.window.focus()

    def on_mouse_up(self) -> None:
        self.remove_class("pressed")
        if self.click_started_on:
            self._move_window_prev()
            self.click_started_on = False

    def on_leave(self) -> None:
        self.remove_class("pressed")
        self.click_started_on = False

    def _move_window_prev(self) -> None:
        """Move this window to the previous position in tiling order (rotate list left)."""
        from textual_window.manager import window_manager

        if window_manager.tiling_layout == TilingLayout.FLOATING:
            return  # No effect in floating mode

        # Get all open windows in the correct order
        open_windows = []
        for window_id in window_manager._window_order:
            if window_id in window_manager._windows and window_manager._windows[window_id].open_state:
                open_windows.append(window_manager._windows[window_id])

        if len(open_windows) <= 1:
            return  # Can't move if only one window

        # Find current window index
        try:
            current_index = open_windows.index(self.window)

            # Remove window from current position
            window = open_windows.pop(current_index)

            # Insert at previous position (rotate left)
            new_index = current_index - 1
            if new_index < 0:
                new_index = len(open_windows)  # Insert at end

            open_windows.insert(new_index, window)

            # Retile with new order
            window_manager._retile_windows_with_order(open_windows)
        except ValueError:
            pass  # Window not found in list


class MoveNextButton(NoSelectStatic):
    """Button for moving window to next position in tiling order."""

    def __init__(self, content: VisualType, window: Window, **kwargs: Any):
        super().__init__(content=content, **kwargs)
        self.window = window
        self.click_started_on: bool = False
        self.tooltip = "Shift This Window Right"

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button == 1:  # left button
            self.click_started_on = True
            self.add_class("pressed")
            self.window.focus()

    def on_mouse_up(self) -> None:
        self.remove_class("pressed")
        if self.click_started_on:
            self._move_window_next()
            self.click_started_on = False

    def on_leave(self) -> None:
        self.remove_class("pressed")
        self.click_started_on = False

    def _move_window_next(self) -> None:
        """Move this window to the next position in tiling order (shift right)."""
        from textual_window.manager import window_manager

        if window_manager.tiling_layout == TilingLayout.FLOATING:
            return  # No effect in floating mode

        # Get all open windows in the correct order
        open_windows = []
        for window_id in window_manager._window_order:
            if window_id in window_manager._windows and window_manager._windows[window_id].open_state:
                open_windows.append(window_manager._windows[window_id])

        if len(open_windows) <= 1:
            return  # Can't move if only one window

        # Find current window index
        try:
            current_index = open_windows.index(self.window)
            total_windows = len(open_windows)

            # Calculate new position (shift right with wraparound)
            new_index = (current_index + 1) % total_windows

            # Swap the windows at current_index and new_index
            open_windows[current_index], open_windows[new_index] = open_windows[new_index], open_windows[current_index]

            # Retile with new order
            window_manager._retile_windows_with_order(open_windows)
        except ValueError:
            pass  # Window not found in list


class ToggleFloatingButton(NoSelectStatic):
    """Button for toggling individual window floating state."""

    def __init__(self, content: VisualType, window: Window, **kwargs: Any):
        super().__init__(content=content, **kwargs)
        self.window = window
        self.click_started_on: bool = False
        self.tooltip = "Toggle Window Floating"

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button == 1:  # left button
            self.click_started_on = True
            self.add_class("pressed")
            self.window.focus()

    def on_mouse_up(self) -> None:
        self.remove_class("pressed")
        if self.click_started_on:
            self._toggle_window_floating()
            self.click_started_on = False

    def on_leave(self) -> None:
        self.remove_class("pressed")
        self.click_started_on = False

    def _toggle_window_floating(self) -> None:
        """Toggle this specific window's participation in tiling."""
        # This would require adding per-window floating state
        # For now, just toggle global tiling mode
        from textual_window.manager import window_manager

        if window_manager.tiling_layout == TilingLayout.FLOATING:
            # Enable tiling with horizontal split as default
            window_manager.set_tiling_layout(TilingLayout.HORIZONTAL_SPLIT)
            self.tooltip = "Disable Tiling"
        else:
            # Disable tiling
            window_manager.set_tiling_layout(TilingLayout.FLOATING)
            self.tooltip = "Enable Tiling"


class RotateLeftButton(NoSelectStatic):
    """Button for rotating the entire window list left."""

    def __init__(self, content: VisualType, window: Window, **kwargs: Any):
        super().__init__(content=content, **kwargs)
        self.window = window
        self.click_started_on: bool = False
        self.tooltip = "Rotate All Windows Left"

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button == 1:  # left button
            self.click_started_on = True
            self.add_class("pressed")
            self.window.focus()

    def on_mouse_up(self) -> None:
        self.remove_class("pressed")
        if self.click_started_on:
            self._rotate_list_left()
            self.click_started_on = False

    def on_leave(self) -> None:
        self.remove_class("pressed")
        self.click_started_on = False

    def _rotate_list_left(self) -> None:
        """Rotate the entire window list left (first window moves to end)."""
        from textual_window.manager import window_manager

        if window_manager.tiling_layout == TilingLayout.FLOATING:
            return  # No effect in floating mode

        # Get all open windows in the correct order
        open_windows = []
        for window_id in window_manager._window_order:
            if window_id in window_manager._windows and window_manager._windows[window_id].open_state:
                open_windows.append(window_manager._windows[window_id])

        if len(open_windows) <= 1:
            return  # Can't rotate if only one window

        # Rotate left: move first window to end
        first_window = open_windows.pop(0)
        open_windows.append(first_window)

        # Retile with new order
        window_manager._retile_windows_with_order(open_windows)


class RotateRightButton(NoSelectStatic):
    """Button for rotating the entire window list right."""

    def __init__(self, content: VisualType, window: Window, **kwargs: Any):
        super().__init__(content=content, **kwargs)
        self.window = window
        self.click_started_on: bool = False
        self.tooltip = "Rotate All Windows Right"

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button == 1:  # left button
            self.click_started_on = True
            self.add_class("pressed")
            self.window.focus()

    def on_mouse_up(self) -> None:
        self.remove_class("pressed")
        if self.click_started_on:
            self._rotate_list_right()
            self.click_started_on = False

    def on_leave(self) -> None:
        self.remove_class("pressed")
        self.click_started_on = False

    def _rotate_list_right(self) -> None:
        """Rotate the entire window list right (last window moves to beginning)."""
        from textual_window.manager import window_manager

        if window_manager.tiling_layout == TilingLayout.FLOATING:
            return  # No effect in floating mode

        # Get all open windows in the correct order
        open_windows = []
        for window_id in window_manager._window_order:
            if window_id in window_manager._windows and window_manager._windows[window_id].open_state:
                open_windows.append(window_manager._windows[window_id])

        if len(open_windows) <= 1:
            return  # Can't rotate if only one window

        # Rotate right: move last window to beginning
        last_window = open_windows.pop()
        open_windows.insert(0, last_window)

        # Retile with new order
        window_manager._retile_windows_with_order(open_windows)


class MinimizeButton(NoSelectStatic):

    def __init__(self, content: VisualType, window: Window, **kwargs: Any):
        super().__init__(content=content, **kwargs)
        self.window = window
        self.click_started_on: bool = False
        self.tooltip = "Minimize"

    def on_mouse_down(self, event: events.MouseDown) -> None:

        if event.button == 1:  # left button
            self.click_started_on = True
            self.add_class("pressed")
            self.window.focus()

    def on_mouse_up(self) -> None:

        self.remove_class("pressed")
        if self.click_started_on:
            self.window.minimize()
            self.click_started_on = False

    def on_leave(self) -> None:

        self.remove_class("pressed")
        self.click_started_on = False


class Resizer(NoSelectStatic):

    def __init__(self, content: VisualType, window: Window, **kwargs: Any) -> None:
        super().__init__(content=content, **kwargs)
        self.window = window
        # Mouse event batching for performance
        self._last_update_time = 0.0
        self._last_mouse_position = Offset(0, 0)
        self._update_pending = False

    def set_max_min(self) -> None:

        assert isinstance(self.window.parent, Widget)
        try:
            self.min_width = self.window.min_width
            self.min_height = self.window.min_height
            self.max_width = self.window.max_width if self.window.max_width else self.window.parent.size.width
            self.max_height = (
                self.window.max_height if self.window.max_height else self.window.parent.size.height
            )
        except AttributeError as e:
            self.log.error(f"{self.window.id} does not have min/max width/height set. ")
            raise e

    def on_mouse_move(self, event: events.MouseMove) -> None:

        # Prevent resize in tiling mode
        if self.window.manager.tiling_layout != TilingLayout.FLOATING:
            return

        # App.mouse_captured refers to the widget that is currently capturing mouse events.
        if self.app.mouse_captured == self:
            # Always track the latest mouse position - never drop events
            self._last_mouse_position = event.screen_offset

            # Schedule update if not already pending
            if not self._update_pending:
                current_time = time.time()

                # Check if enough time has passed for immediate update (60fps = ~16.67ms)
                if current_time - self._last_update_time >= 0.0167:
                    self._apply_resize()
                else:
                    # Schedule for next frame
                    self._update_pending = True
                    self.call_after_refresh(self._apply_resize)

    def _apply_resize(self) -> None:
        """Apply resize based on latest mouse position."""
        assert isinstance(self.window.parent, Widget)
        assert self.window.styles.width is not None
        assert self.window.styles.height is not None

        total_delta = self._last_mouse_position - self.position_on_down
        new_size = self.size_on_down + total_delta

        self.window.styles.width = clamp(new_size.width, self.min_width, self.max_width)
        self.window.styles.height = clamp(new_size.height, self.min_height, self.max_height)

        # Reset for next batch
        self._last_update_time = time.time()
        self._update_pending = False

            # * Explanation:
            # Get the absolute position of the mouse right now (event.screen_offset),
            # minus where it was when the mouse was pressed down (position_on_down).
            # That gives the total delta from the original position.
            # Note that this is not the same as the event.delta attribute,
            # that only gives you the delta from the last mouse move event.
            # But we need the total delta from the original position.
            # Once we have that, add the total delta to size of the window.
            # If total_delta is negative, the size will be smaller

    def on_mouse_down(self, event: events.MouseDown) -> None:

        # Prevent resize in tiling mode
        if self.window.manager.tiling_layout != TilingLayout.FLOATING:
            return

        if event.button == 1:  # left button
            self.position_on_down = event.screen_offset
            self.size_on_down = self.window.size

            self.add_class("pressed")
            self.capture_mouse()
            self.window.focus()

    def on_mouse_up(self) -> None:

        self.remove_class("pressed")
        self.release_mouse()
        self.window.clamp_into_parent_area()  # Clamp to parent if resizing put it out of bounds


class TitleBar(NoSelectStatic):

    def __init__(self, window_title: str, window: Window, **kwargs: Any):
        super().__init__(content=window_title, **kwargs)
        self.window = window
        # Mouse event batching for performance
        self._last_update_time = 0.0
        self._accumulated_delta = Offset(0, 0)
        self._update_pending = False

    def on_mouse_move(self, event: events.MouseMove) -> None:

        if self.app.mouse_captured == self:
            # Always accumulate movement - never drop events
            self._accumulated_delta += event.delta

            # Schedule update if not already pending
            if not self._update_pending:
                current_time = time.time()

                # Check if enough time has passed for immediate update (60fps = ~16.67ms)
                if current_time - self._last_update_time >= 0.0167:
                    self._apply_accumulated_movement()
                else:
                    # Schedule for next frame
                    self._update_pending = True
                    self.call_after_refresh(self._apply_accumulated_movement)

    def _apply_accumulated_movement(self) -> None:
        """Apply all accumulated movement in a single operation."""
        if self._accumulated_delta != Offset(0, 0):
            # Simple approach: just use normal CSS offset with batching
            if not self.window.snap_state:  # not locked, can move freely
                self.window.offset = self.window.offset + self._accumulated_delta
            else:  # else, if locked to parent:
                assert isinstance(self.window.parent, Widget)
                self.window.offset = self.window.offset + self._accumulated_delta  # first move into place normally
                self.window.clamp_into_parent_area()  # then clamp back to parent area.

        # Reset for next batch
        self._accumulated_delta = Offset(0, 0)
        self._last_update_time = time.time()
        self._update_pending = False

                # Setting the offset and then clamping it again afterwards might not seem efficient,
                # but it looks the best, and least glitchy. I tried doing it in a single operation, and
                # it didn't work as well, or look as good.

    def on_mouse_down(self, event: events.MouseDown) -> None:

        if event.button == 1:  # left button
            self.add_class("pressed")
            self.capture_mouse()
            self.window.focus()

    def on_mouse_up(self) -> None:

        self.remove_class("pressed")
        self.release_mouse()


class TopBar(Horizontal):

    def __init__(  # passing in window might seem redundant because of self.parent,
        self,  # but it gives better type hinting and allows for more advanced
        window: Window,  # dependeny injection of the window down to children widgets.
        window_title: str,
        options: dict[str, Callable[..., Optional[Any]]] | None,
    ):
        super().__init__()
        self.window = window
        self.window_title = (window.icon + " " + window_title) if window.icon else window_title
        self.options = options

    def compose(self) -> ComposeResult:

        yield TitleBar(self.window_title, window=self.window)
        if self.options:
            yield HamburgerButton(
                BUTTON_SYMBOLS["hamburger"], window=self.window, options=self.options, classes="windowbutton"
            )
        # Add tiling control buttons
        yield MovePrevButton(BUTTON_SYMBOLS["move_prev"], window=self.window, classes="windowbutton")
        yield MoveNextButton(BUTTON_SYMBOLS["move_next"], window=self.window, classes="windowbutton")
        yield RotateLeftButton(BUTTON_SYMBOLS["rotate_left"], window=self.window, classes="windowbutton")
        yield RotateRightButton(BUTTON_SYMBOLS["rotate_right"], window=self.window, classes="windowbutton")
        yield TilingButton(BUTTON_SYMBOLS["tiling"], window=self.window, classes="windowbutton")
        yield ToggleFloatingButton(BUTTON_SYMBOLS["toggle_floating"], window=self.window, classes="windowbutton")
        yield MinimizeButton(BUTTON_SYMBOLS["minimize"], window=self.window, classes="windowbutton")
        if self.window.allow_maximize_window:
            self.maximize_button = MaximizeButton(
                BUTTON_SYMBOLS["maximize"], window=self.window, classes="windowbutton"
            )
            yield self.maximize_button
        if self.window.window_mode == "temporary":
            yield CloseButton(BUTTON_SYMBOLS["close"], window=self.window, classes="windowbutton close")


class BottomBar(Horizontal):

    def __init__(self, window: Window):
        super().__init__()
        self.window = window

    def compose(self) -> ComposeResult:
        yield NoSelectStatic(id="bottom_bar_text")
        if self.window.allow_resize:
            yield Resizer(BUTTON_SYMBOLS["resizer"], window=self.window, classes="windowbutton")
