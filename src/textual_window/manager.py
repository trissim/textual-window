"""Module for the Window Manager.

You don't need to import from this module. You can simply do:
`from textual_window import window_manager`.
It is a singleton. Do not use the WindowManager class directly.

Note that you can also access the window manager from any window,
or the Window Bar, with `self.manager`. The same instance is attached
to all of them."""

# ~ Type Checking (Pyright and MyPy) - Strict Mode
# ~ Linting - Ruff
# ~ Formatting - Black - max 110 characters / line

# Python imports
from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Awaitable, List

if TYPE_CHECKING:
    from textual_window.window import Window
    from textual_window.windowbar import WindowBar
    import rich.repr

# Local imports
from textual_window.tiling import TilingLayout, calculate_tiling_positions

# Textual imports
from textual.dom import DOMNode
from textual.reactive import reactive
from textual.geometry import Offset, Size
from textual.binding import Binding

__all__ = [
    "window_manager",
]


class WindowManager(DOMNode):
    """! Do not import this class directly. Use the `window_manager` instance instead.

    This class is the blueprint for a singleton instance used internally by the
    library for all of the windows to register themselves, so they can appear automatically
    on the WindowBar. The library is designed so there is no need for you to interact
    directly with the manager.

    Everything this manager does is fully automated. There shouldn't be any real need
    to use or interact with it directly. It is used by windows and the WindowBar to
    manage everything.

    If you want to interact with the window manager directly for some reason, you can
    import the `window_manager` instance:
    ```py
    from textual_window import window_manager
    ```"""

    # Reactive properties
    tiling_layout: reactive[TilingLayout] = reactive(TilingLayout.FLOATING)
    """The current tiling layout mode for automatic window arrangement."""

    window_gap: reactive[int] = reactive(0)
    """The vertical gap size in pixels around and between tiled windows. Horizontal gap is automatically 2x this value."""



    def __init__(self) -> None:
        super().__init__()

        #! self._windows could possibly be reactive?
        self._windows: dict[str, Window] = {}  # Dictionary to store windows by their ID
        self._window_order: list[str] = []  # Track window order for tiling
        self._windowbar: WindowBar | None = None
        self._last_focused_window: Window | None = None
        self._recent_focus_order: list[Window] = []
        self._mounting_callbacks: dict[str, Callable[[Window], Awaitable[None]]] = {}

        # These 3 variables are just used to keep track of the closing process.
        # All 3 get reset every time the process finishes.
        self._closing_in_progress = False
        self._num_of_temporary_windows = 0
        self._checked_in_closing_windows = 0

    ##################
    # ~ Properties ~ #
    ##################

    @property
    def windows(self) -> dict[str, Window]:
        """Get the dictionary of all windows."""
        return self._windows

    @property
    def windowbar(self) -> WindowBar | None:
        """Get the windowbar instance."""
        return self._windowbar

    @property
    def recent_window_focus_order(self) -> list[Window]:
        """Get the list of windows in the order they were most recently focused."""
        # called by Window.compose()
        return self._recent_focus_order

    @property
    def last_focused_window(self) -> Window | None:
        """Get the last focused window."""
        # called by Window.action_confirm()
        return self._last_focused_window

    @last_focused_window.setter
    def last_focused_window(self, window: Window) -> None:
        """Set the last focused window."""
        # called by Window._on_focus()
        self._last_focused_window = window

    #######################
    # ~ Container Methods #
    #######################

    def register_mounting_callback(
        self,
        callback: Callable[[Window], Awaitable[None]],
        callback_id: str,
    ) -> None:
        """Register a callback which can be used by the Window Manager to mount windows
        that are passed into it with the `mount_window` method.

        Args:
            callback (Callable[[Window], None]): The callback function that will be called
                when a window is mounted. It should accept a single argument, which is the
                `Window` instance to be mounted.
            callback_id (str): A unique identifier for the callback. This is used to identify the
                callback when mounting a window. It should be unique for each callback.
        Raises:
            KeyError: If a callback with the same ID already exists.

        """

        if callback_id in self._mounting_callbacks:
            self.log.warning(
                f"func register_mounting_callback: Callback with ID {callback_id} already exists. "
                "Overwriting the existing callback."
            )
        self._mounting_callbacks[callback_id] = callback
        self.log.debug(f"func register_mounting_callback: Registered mounting callback for {callback_id}.")

    def mount_window(self, window: Window, callback_id: str) -> None:
        """Mount a window using a callback registered with the `register_mounting_callback`
        method.
        This allows the manager to handle the mounting of windows without needing to mount them
        directly into their destination. If you have a process manager of some sort that creates
        and manages windows, this allows the process manager to just send them to the window manager.

        Args:
            window (Window): The window to be mounted.
            callback_id (str): The ID of the callback to be used for mounting the window. This would be whatever
                ID you used when registering the callback with `register_mounting_callback`.
        Raises:
            KeyError: If no callback with the given ID is registered.
        """

        try:
            self.log.debug(f"func mount_window: Mounting window {window.id} with callback {callback_id}.")
            callback = self._mounting_callbacks[callback_id]
            callback(window)
        except KeyError as e:
            self.log.error(
                f"func mount_window: No mounting callback registered for "
                f"ID '{callback_id}'. Window {window.id} was not mounted."
            )
            raise KeyError(f"No mounting callback registered for ID '{callback_id}'.") from e

    #########################
    # ~ WindowBar Methods ~ #
    #########################

    def register_windowbar(self, windowbar: WindowBar) -> None:
        """Register the windowbar with the manager. This is done automatically when the
        windowbar is mounted. You shouldn't need to call this manually.

        Note that there can only be one windowbar in the app. If you try to mount a second
        windowbar, it will raise an error. It is not designed to be used that way.
        Multiple windowbars with different windows on them is an interesting idea, but it's not
        currently supported."""
        # called by Window.__init__()

        if not self._windowbar:
            self.log.debug("func register_windowbar: Registering windowbar with the manager.")
            self._windowbar = windowbar
        else:
            raise RuntimeError(
                "There is already a WindowBar registered with the WindowManager. "
                "You cannot have more than one WindowBar in the app."
            )

    def unregister_windowbar(self) -> None:
        """Unregister the windowbar from the manager. This is done automatically when the
        windowbar is unmounted. You shouldn't need to call this manually."""
        # called by Window._on_unmount()

        if self._windowbar:
            self.log.debug("func unregister_windowbar: Unregistering windowbar from the manager.")
            self._windowbar = None
        else:
            raise RuntimeError(
                "There is no WindowBar registered with the WindowManager. "
                "You cannot unregister a WindowBar that is not registered."
            )

    def signal_window_state(self, window: Window, state: bool) -> None:
        """This method triggers the WindowBar to update the window's button on the bar
        when a window is minimized or maximized to show its current state (adds or
        removes the dot.)"""
        # called by Window._dom_ready(), _open_animation(), _close_animation()

        if self._windowbar:
            self._windowbar.update_window_button_state(window, state)

        # Trigger retiling when windows open/close if tiling is active
        if self.tiling_layout != TilingLayout.FLOATING:
            self._retile_all_windows()

    ######################
    # ~ Window Methods ~ #
    ######################

    async def window_ready(self, window: Window) -> bool | None:
        # called by Window._dom_ready()

        result = None
        if self._windowbar:
            button_worker = self._windowbar.add_window_button(window)  # type: ignore[unused-ignore]
            await button_worker.wait()
            result = True

        # Trigger retiling when new windows are fully initialized
        if self.tiling_layout != TilingLayout.FLOATING:
            self._retile_all_windows()

        return result

    def register_window(self, window: Window) -> None:
        """Used by windows to register with the manager.
        Windows do this automatically when they are mounted. There should not be any
        need to call this method manually."""
        # called by Window.__init__()

        if window.id:
            self._windows[window.id] = window
            # Add to window order for tiling
            if window.id not in self._window_order:
                self._window_order.append(window.id)
        else:
            raise ValueError(
                "Window ID is not set. "
                "Please set the ID of the window before registering it with the manager."
            )
        self._recent_focus_order.append(window)

    def unregister_window(self, window: Window) -> None:
        """Used by windows to unregister with the manager.
        Windows do this automatically when they are unmounted. There should not be any
        need to call this method manually."""
        # called by Window._execute_remove()

        if window.id in self._windows:
            self._windows.pop(window.id)
            # Remove from window order for tiling
            if window.id in self._window_order:
                self._window_order.remove(window.id)
            self.log.debug(f"func unregister_window: Unregistered {window.id} from the manager.")
        else:
            raise ValueError(
                "Window ID not found in the manager. "
                "Please make sure the window is registered with the manager before unregistering it."
            )
        if window in self._recent_focus_order:
            self._recent_focus_order.remove(window)

        if self._windowbar:
            self._windowbar.remove_window_button(window)  # type: ignore[unused-ignore]

        if self._closing_in_progress:
            if window.window_mode == "temporary":  # <- this shouldn't be necessary.
                self._checked_in_closing_windows += 1

            if self._checked_in_closing_windows == self._num_of_temporary_windows:
                self._checked_in_closing_windows = 0
                self._num_of_temporary_windows = 0
                self.call_after_refresh(lambda: setattr(self, "closing_in_progress", False))

        # Trigger retiling when windows are removed
        if self.tiling_layout != TilingLayout.FLOATING:
            self._retile_all_windows()

    def change_window_focus_order(self, window: Window) -> None:
        """recent_focus_order attribute is read by the WindowSwitcher to display
        the windows in the order they were most recently focused."""
        # called by Window._on_focus()

        if self._recent_focus_order:
            if window in self._recent_focus_order:
                self._recent_focus_order.remove(window)
            self._recent_focus_order.insert(0, window)
        else:
            if not self._closing_in_progress:
                raise RuntimeError(
                    "No windows in the recent focus order. "
                    "This should not happen. Please report this issue."
                )
        self._last_focused_window = window

    def __rich_repr__(self) -> rich.repr.Result:
        yield "windows", self._windows
        yield "layers", self.app.screen.styles.layers

    def get_windows_as_dict(self) -> dict[str, Window]:
        """Get a dictionary of all windows."""
        return self._windows

    def get_windows_as_list(self) -> list[Window]:
        """Get a list of all windows."""
        windows = [window for window in self._windows.values()]
        return windows

    #############################
    # ~ Actions for all windows ~
    #############################

    # These are all called by WindowBar.buttonpressed()
    jump_clicker: type[WindowBar]  # noqa: F842 # type: ignore

    def open_all_windows(self) -> None:
        """Open all windows."""

        for window in self._windows.values():
            window.open_state = True

    def close_all_windows(self) -> None:
        """Close all windows. This will close all temporary windows and
        minimize all permanent windows."""

        # First we need to count how many temporary windows there are.
        # It counts them as they unregister so it knows when it can set
        # closing_in_progress back to False.
        self._num_of_temporary_windows = len(
            [w for w in self._windows.values() if w.window_mode == "temporary"]
        )

        # This makes a copy because otherwise it would get smaller
        # while iterating over it.
        windows_copy = self._windows.copy()

        self._closing_in_progress = True
        for window in windows_copy.values():
            if window.window_mode == "temporary":
                window.remove_window()
            else:
                window.open_state = False

    def minimize_all_windows(self) -> None:
        """Minimize all windows."""

        for window in self._windows.values():
            window.open_state = False

    def snap_all_windows(self) -> None:
        """Snap/Lock all windows."""

        for window in self._windows.values():
            window.snap_state = True

    def unsnap_all_windows(self) -> None:
        """Unsnap/Unlock all windows."""

        for window in self._windows.values():
            window.snap_state = False

    async def reset_all_windows(self) -> None:
        """Reset all windows to their starting position and size."""

        for window in self._windows.values():
            await window.reset_window()

    #########################
    # ~ Tiling Methods ~ #
    #########################

    def get_tiling_position(self, window: Window) -> Offset:
        """Get the tiling position for a specific window.

        Args:
            window: The window to get the position for

        Returns:
            Offset representing the window's position in the current tiling layout

        Raises:
            ValueError: If window is not found in tiling calculation results
        """
        if self.tiling_layout == TilingLayout.FLOATING:
            raise ValueError("Cannot get tiling position when in floating mode")

        # Get all open windows for tiling calculation
        open_windows = [w for w in self._windows.values() if w.open_state]

        if not open_windows:
            return Offset(0, 0)

        # Calculate tiling positions for all windows
        # Use available screen space and account for UI bar offset
        from textual_window.window import calculate_available_screen_space, calculate_window_container_offset
        container_size = calculate_available_screen_space(self.app)
        container_offset = calculate_window_container_offset(self.app)
        try:
            positions = calculate_tiling_positions(open_windows, self.tiling_layout, container_size, self.window_gap)
        except ValueError as e:
            # Graceful degradation: fall back to floating mode on tiling calculation failure
            self.log.warning(f"Tiling calculation failed, falling back to floating mode: {e}")
            self.tiling_layout = TilingLayout.FLOATING
            raise ValueError(f"Tiling calculation failed: {e}")

        if window.id not in positions:
            raise ValueError(f"Window {window.id} not found in tiling calculation results")

        position, _ = positions[window.id]
        # Adjust position by container offset to account for UI bars
        adjusted_position = Offset(position.x + container_offset.x, position.y + container_offset.y)
        return adjusted_position

    def get_tiling_size(self, window: Window) -> Size:
        """Get the tiling size for a specific window.

        Args:
            window: The window to get the size for

        Returns:
            Size representing the window's size in the current tiling layout

        Raises:
            ValueError: If window is not found in tiling calculation results
        """
        if self.tiling_layout == TilingLayout.FLOATING:
            raise ValueError("Cannot get tiling size when in floating mode")

        # Get all open windows for tiling calculation
        open_windows = [w for w in self._windows.values() if w.open_state]

        if not open_windows:
            return Size(0, 0)

        # Calculate tiling positions for all windows
        # Use available screen space instead of full screen size
        from textual_window.window import calculate_available_screen_space
        container_size = calculate_available_screen_space(self.app)
        try:
            positions = calculate_tiling_positions(open_windows, self.tiling_layout, container_size, self.window_gap)
        except ValueError as e:
            # Graceful degradation: fall back to floating mode on tiling calculation failure
            self.log.warning(f"Tiling calculation failed, falling back to floating mode: {e}")
            self.tiling_layout = TilingLayout.FLOATING
            raise ValueError(f"Tiling calculation failed: {e}")

        if window.id not in positions:
            raise ValueError(f"Window {window.id} not found in tiling calculation results")

        _, size = positions[window.id]
        return size

    def _retile_all_windows(self) -> None:
        """Retile all open windows according to the current tiling layout.

        This method recalculates positions and sizes for all open windows
        and applies them immediately. Follows the pattern of bulk operations
        like minimize_all_windows().
        """
        if self.tiling_layout == TilingLayout.FLOATING:
            return  # No retiling needed in floating mode

        # Get all open windows for tiling in the correct order
        open_windows = []
        for window_id in self._window_order:
            if window_id in self._windows and self._windows[window_id].open_state:
                open_windows.append(self._windows[window_id])

        if not open_windows:
            return  # No windows to retile

        # Calculate new positions and sizes for all windows
        # Use available screen space and account for UI bar offset
        from textual_window.window import calculate_available_screen_space, calculate_window_container_offset
        container_size = calculate_available_screen_space(self.app)
        container_offset = calculate_window_container_offset(self.app)
        try:
            positions = calculate_tiling_positions(open_windows, self.tiling_layout, container_size, self.window_gap)
        except ValueError as e:
            # Graceful degradation: fall back to floating mode on tiling calculation failure
            self.log.warning(f"Retiling failed, falling back to floating mode: {e}")
            self.tiling_layout = TilingLayout.FLOATING
            return

        # Apply new positions and sizes to each window
        for window in open_windows:
            if window.id in positions:
                position, size = positions[window.id]

                # Update window size
                window.styles.width = size.width
                window.styles.height = size.height

                # Update window position (adjust by container offset to account for UI bars)
                adjusted_position = Offset(position.x + container_offset.x, position.y + container_offset.y)
                window.offset = adjusted_position

                # Update stored size values for consistency
                window.starting_width = size.width
                window.starting_height = size.height

    def _retile_windows_with_order(self, ordered_windows: List[Window]) -> None:
        """Retile windows using a specific order.

        This method allows reordering windows in the tiling layout.

        Args:
            ordered_windows: List of windows in the desired order
        """
        if self.tiling_layout == TilingLayout.FLOATING:
            return  # No retiling needed in floating mode

        if not ordered_windows:
            return  # No windows to retile

        # Update the internal window order to match the new order
        new_order = [w.id for w in ordered_windows]
        # Keep windows not in the ordered list at the end
        for window_id in self._window_order:
            if window_id not in new_order:
                new_order.append(window_id)
        self._window_order = new_order

        # Calculate new positions and sizes for windows in the specified order
        # Use available screen space and account for UI bar offset
        from textual_window.window import calculate_available_screen_space, calculate_window_container_offset
        container_size = calculate_available_screen_space(self.app)
        container_offset = calculate_window_container_offset(self.app)
        try:
            positions = calculate_tiling_positions(ordered_windows, self.tiling_layout, container_size, self.window_gap)
        except ValueError as e:
            # Graceful degradation: fall back to floating mode on tiling calculation failure
            self.log.warning(f"Retiling with order failed, falling back to floating mode: {e}")
            self.tiling_layout = TilingLayout.FLOATING
            return

        # Apply new positions and sizes to each window
        for window in ordered_windows:
            if window.id in positions:
                position, size = positions[window.id]

                # Update window size
                window.styles.width = size.width
                window.styles.height = size.height

                # Update window position (adjust by container offset to account for UI bars)
                adjusted_position = Offset(position.x + container_offset.x, position.y + container_offset.y)
                window.offset = adjusted_position

                # Update stored size values for consistency
                window.starting_width = size.width
                window.starting_height = size.height

    def watch_tiling_layout(self, value: TilingLayout) -> None:
        """Reactive watcher for tiling layout changes.

        When the tiling layout changes, automatically retile all windows
        to apply the new layout.

        Args:
            value: The new TilingLayout value
        """
        if value != TilingLayout.FLOATING:
            # Handle state conflicts: restore maximized windows before tiling
            self._handle_state_conflicts_before_tiling()

            # Only retile if we have windows and are switching to a tiling mode
            if self._windows:
                self._retile_all_windows()

    def watch_window_gap(self, value: int) -> None:
        """Reactive watcher for window gap changes.

        When the window gap changes, automatically retile all windows
        to apply the new gap spacing.

        Args:
            value: The new gap value in pixels
        """
        if self.tiling_layout != TilingLayout.FLOATING:
            # Only retile if we're in a tiling mode and have windows
            if self._windows:
                self._retile_all_windows()

    def _handle_state_conflicts_before_tiling(self) -> None:
        """Handle state conflicts before applying tiling.

        Restores maximized windows to their normal state so they can be tiled properly.
        """
        for window in self._windows.values():
            if window.maximize_state:
                # Restore maximized windows so they can be tiled
                window.maximize_state = False

    #################################
    # ~ Tiling Mode Switching API ~ #
    #################################

    def set_tiling_layout(self, layout: TilingLayout) -> None:
        """Set the tiling layout mode programmatically.

        Args:
            layout: The TilingLayout to switch to
        """
        self.tiling_layout = layout

    #############################
    # ~ Focus Navigation API ~ #
    #############################

    def focus_next_window(self) -> None:
        """Focus the next window in the recent focus order."""
        if not self._recent_focus_order:
            return

        current = self._last_focused_window
        if not current:
            # Focus first window if none focused
            self._recent_focus_order[0].focus()
            return

        try:
            current_index = self._recent_focus_order.index(current)
            next_index = (current_index + 1) % len(self._recent_focus_order)
            next_window = self._recent_focus_order[next_index]
            if next_window.open_state:
                next_window.focus()
        except (ValueError, IndexError):
            # Fallback to first window
            if self._recent_focus_order:
                self._recent_focus_order[0].focus()

    def focus_previous_window(self) -> None:
        """Focus the previous window in the recent focus order."""
        if not self._recent_focus_order:
            return

        current = self._last_focused_window
        if not current:
            # Focus last window if none focused
            self._recent_focus_order[-1].focus()
            return

        try:
            current_index = self._recent_focus_order.index(current)
            prev_index = (current_index - 1) % len(self._recent_focus_order)
            prev_window = self._recent_focus_order[prev_index]
            if prev_window.open_state:
                prev_window.focus()
        except (ValueError, IndexError):
            # Fallback to last window
            if self._recent_focus_order:
                self._recent_focus_order[-1].focus()

    ################################
    # ~ Window Movement API ~ #
    ################################

    def move_focused_window_prev(self) -> None:
        """Move the currently focused window to the previous position in tiling order."""
        if not self._last_focused_window or self.tiling_layout == TilingLayout.FLOATING:
            return  # No effect in floating mode or no focused window

        # Get all open windows in the correct order
        open_windows = []
        for window_id in self._window_order:
            if window_id in self._windows and self._windows[window_id].open_state:
                open_windows.append(self._windows[window_id])

        if len(open_windows) <= 1:
            return  # Can't move if only one window

        # Find current window index
        try:
            current_index = open_windows.index(self._last_focused_window)

            # Remove window from current position
            window = open_windows.pop(current_index)

            # Insert at previous position (shift left, wrap around to end if at beginning)
            new_index = (current_index - 1) % len(open_windows)
            open_windows.insert(new_index, window)

            # Retile with new order
            self._retile_windows_with_order(open_windows)
        except ValueError:
            pass  # Window not found in list

    def move_focused_window_next(self) -> None:
        """Move the currently focused window to the next position in tiling order."""
        if not self._last_focused_window or self.tiling_layout == TilingLayout.FLOATING:
            return  # No effect in floating mode or no focused window

        # Get all open windows in the correct order
        open_windows = []
        for window_id in self._window_order:
            if window_id in self._windows and self._windows[window_id].open_state:
                open_windows.append(self._windows[window_id])

        if len(open_windows) <= 1:
            return  # Can't move if only one window

        # Find current window index
        try:
            current_index = open_windows.index(self._last_focused_window)

            # Remove window from current position
            window = open_windows.pop(current_index)

            # Insert at next position (shift right, wrap around to beginning if at end)
            new_index = current_index % len(open_windows)
            open_windows.insert(new_index, window)

            # Retile with new order
            self._retile_windows_with_order(open_windows)
        except ValueError:
            pass  # Window not found in list

    def rotate_window_order_left(self) -> None:
        """Rotate all windows left in the tiling order."""
        if self.tiling_layout == TilingLayout.FLOATING:
            return  # No effect in floating mode

        # Get all open windows in the correct order
        open_windows = []
        for window_id in self._window_order:
            if window_id in self._windows and self._windows[window_id].open_state:
                open_windows.append(self._windows[window_id])

        if len(open_windows) <= 1:
            return  # Can't rotate if only one window

        # Rotate left: move first window to end
        rotated_windows = open_windows[1:] + [open_windows[0]]

        # Retile with new order
        self._retile_windows_with_order(rotated_windows)

    def rotate_window_order_right(self) -> None:
        """Rotate all windows right in the tiling order."""
        if self.tiling_layout == TilingLayout.FLOATING:
            return  # No effect in floating mode

        # Get all open windows in the correct order
        open_windows = []
        for window_id in self._window_order:
            if window_id in self._windows and self._windows[window_id].open_state:
                open_windows.append(self._windows[window_id])

        if len(open_windows) <= 1:
            return  # Can't rotate if only one window

        # Rotate right: move last window to beginning
        rotated_windows = [open_windows[-1]] + open_windows[:-1]

        # Retile with new order
        self._retile_windows_with_order(rotated_windows)

    ############################
    # ~ Gap Adjustment API ~ #
    ############################

    def adjust_window_gap(self, delta: int) -> None:
        """Adjust the window gap by the specified delta.

        Args:
            delta: Amount to change the gap (positive to increase, negative to decrease)
        """
        new_gap = max(0, self.window_gap + delta)  # Ensure gap doesn't go below 0
        try:
            self.set_window_gap(new_gap)
        except ValueError:
            # Gap would be too large, ignore the adjustment
            pass

    def get_tiling_layout(self) -> TilingLayout:
        """Get the current tiling layout mode.

        Returns:
            The current TilingLayout
        """
        return self.tiling_layout

    def enable_tiling(self, layout: TilingLayout) -> None:
        """Enable tiling with the specified layout.

        Args:
            layout: The TilingLayout to enable (must not be FLOATING)

        Raises:
            ValueError: If layout is FLOATING
        """
        if layout == TilingLayout.FLOATING:
            raise ValueError("Cannot enable tiling with FLOATING layout. Use disable_tiling() instead.")
        self.tiling_layout = layout

    def disable_tiling(self) -> None:
        """Disable tiling and return to floating window mode."""
        self.tiling_layout = TilingLayout.FLOATING

    def set_window_gap(self, gap: int) -> None:
        """Set the vertical gap around and between tiled windows.

        Args:
            gap: Vertical gap size in pixels around and between windows (must be >= 0).
                 Horizontal gap is automatically set to 2x this value.

        Raises:
            ValueError: If gap is negative or would make windows too small
        """
        if gap < 0:
            raise ValueError(f"Window gap must be >= 0, got: {gap}")

        # Validate gap doesn't violate minimum window sizes if tiling is active
        if self.tiling_layout != TilingLayout.FLOATING and self._windows:
            open_windows = [w for w in self._windows.values() if w.open_state]
            if open_windows:
                # Use available screen space instead of full screen size
                from textual_window.window import calculate_available_screen_space
                container_size = calculate_available_screen_space(self.app)
                try:
                    # Test if the gap would work with current layout
                    calculate_tiling_positions(open_windows, self.tiling_layout, container_size, gap)
                except ValueError as e:
                    raise ValueError(f"Gap {gap} is too large for current layout: {e}")

        self.window_gap = gap

    def get_window_gap(self) -> int:
        """Get the current vertical gap around and between tiled windows.

        Returns:
            The current vertical gap size in pixels. Horizontal gap is 2x this value.
        """
        return self.window_gap




window_manager = WindowManager()  # ~ <-- Create a window manager instance.
"""Global Window Manager for all the windows in the application.  
This is a singleton instance that can be used throughout the application to manage
windows. It is used by the WindowBar widget to display all windows on the bar and let
you manage them, and it is also attached to each window with the self.manager attribute.  
It is not necessary to use the manager instance directly. However, it is
available to import if you want to use it for whatever reason.

To import:
```python
from textual_window import window_manager
```
"""
