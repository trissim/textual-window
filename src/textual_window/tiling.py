"""Tiling window manager functionality for textual-window.

This module provides tiling layout calculations and enums for automatic
window arrangement in predefined layouts.
"""

# ~ Type Checking (Pyright and MyPy) - Strict Mode
# ~ Linting - Ruff
# ~ Formatting - Black - max 110 characters / line

# Python imports
from __future__ import annotations
from typing import TYPE_CHECKING, Dict, List, Tuple
from enum import Enum
import math

if TYPE_CHECKING:
    from textual_window.window import Window

# Textual imports
from textual.geometry import Offset, Size

__all__ = [
    "TilingLayout",
    "calculate_tiling_positions",
]


class TilingLayout(Enum):
    """Enumeration of available tiling layout modes."""
    
    FLOATING = "floating"
    """Default floating window mode - windows position themselves independently."""
    
    HORIZONTAL_SPLIT = "horizontal_split"
    """Split screen horizontally - windows arranged side by side."""
    
    VERTICAL_SPLIT = "vertical_split"
    """Split screen vertically - windows arranged top to bottom."""
    
    GRID = "grid"
    """Grid layout - windows arranged in a grid pattern."""
    
    MASTER_DETAIL = "master_detail"
    """Master-detail layout - one large master window with smaller detail windows."""


def calculate_tiling_positions(
    windows: List[Window],
    layout: TilingLayout,
    container_size: Size,
    gap: int = 0
) -> Dict[str, Tuple[Offset, Size]]:
    """Calculate tiling positions and sizes for a list of windows.

    This is a pure function that takes window list, layout mode, container
    size and returns position/size mappings for each window.

    Args:
        windows: List of Window objects to arrange
        layout: TilingLayout enum specifying the arrangement mode
        container_size: Size of the container (screen) to arrange windows within
        gap: Vertical gap size in pixels. Creates gaps between windows AND around the edges.
             Horizontal gap is automatically 2x this value (default: 0)

    Returns:
        Dictionary mapping window IDs to (position, size) tuples

    Raises:
        ValueError: If layout is not supported or windows list is invalid
    """
    # Handle edge cases
    if not windows:
        return {}

    if layout == TilingLayout.FLOATING:
        # Floating mode - return empty dict to use normal positioning
        return {}

    # Validate container size
    if container_size.width <= 0 or container_size.height <= 0:
        raise ValueError(f"Invalid container size: {container_size}")

    # Validate gap parameter
    if gap < 0:
        raise ValueError(f"Gap must be >= 0, got: {gap}")

    window_count = len(windows)
    result: Dict[str, Tuple[Offset, Size]] = {}

    # Calculate gap values: horizontal gap is 2x vertical gap
    vertical_gap = gap
    horizontal_gap = gap * 2

    # Ensure minimum window sizes
    min_window_width = 12  # Minimum usable window width
    min_window_height = 6  # Minimum usable window height

    # Validate that gaps don't consume too much space
    if layout == TilingLayout.HORIZONTAL_SPLIT:
        total_gap_space = 2 * horizontal_gap + horizontal_gap * (window_count - 1)
        available_width = container_size.width - total_gap_space
        available_height = container_size.height - 2 * vertical_gap
        min_required_width = window_count * min_window_width
        if available_width < min_required_width or available_height < min_window_height:
            raise ValueError(f"Gap too large for horizontal split: {gap} vertical gap (horizontal={horizontal_gap}) with {window_count} windows requires {total_gap_space + min_required_width} width and {2 * vertical_gap + min_window_height} height, but container is only {container_size.width}x{container_size.height}")

    elif layout == TilingLayout.VERTICAL_SPLIT:
        total_gap_space = 2 * vertical_gap + vertical_gap * (window_count - 1)
        available_height = container_size.height - total_gap_space
        available_width = container_size.width - 2 * horizontal_gap
        min_required_height = window_count * min_window_height
        if available_height < min_required_height or available_width < min_window_width:
            raise ValueError(f"Gap too large for vertical split: {gap} vertical gap (horizontal={horizontal_gap}) with {window_count} windows requires {2 * horizontal_gap + min_window_width} width and {total_gap_space + min_required_height} height, but container is only {container_size.width}x{container_size.height}")

    elif layout == TilingLayout.GRID:
        cols = math.ceil(math.sqrt(window_count))
        rows = math.ceil(window_count / cols)
        total_horizontal_gap_space = 2 * horizontal_gap + horizontal_gap * (cols - 1)
        total_vertical_gap_space = 2 * vertical_gap + vertical_gap * (rows - 1)
        available_width = container_size.width - total_horizontal_gap_space
        available_height = container_size.height - total_vertical_gap_space
        min_required_width = cols * min_window_width
        min_required_height = rows * min_window_height
        if available_width < min_required_width or available_height < min_required_height:
            raise ValueError(f"Gap too large for grid layout: {gap} vertical gap (horizontal={horizontal_gap}) with {cols}x{rows} grid requires {total_horizontal_gap_space + min_required_width}x{total_vertical_gap_space + min_required_height} minimum, but container is {container_size.width}x{container_size.height}")

    elif layout == TilingLayout.MASTER_DETAIL and window_count > 1:
        detail_count = window_count - 1
        total_detail_gap_space = 2 * vertical_gap + vertical_gap * (detail_count - 1)
        available_detail_height = container_size.height - total_detail_gap_space
        min_required_detail_height = detail_count * min_window_height
        total_width = container_size.width - 2 * horizontal_gap
        master_width = int(total_width * 0.6)
        detail_width = total_width - master_width - horizontal_gap
        if available_detail_height < min_required_detail_height:
            raise ValueError(f"Gap too large for master-detail layout: {gap} vertical gap with {detail_count} detail windows requires {total_detail_gap_space + min_required_detail_height} height, but container is {container_size.height}")
        if detail_width < min_window_width or master_width < min_window_width:
            raise ValueError(f"Gap too large for master-detail layout: {gap} vertical gap (horizontal={horizontal_gap}) leaves master width {master_width} or detail width {detail_width} < minimum {min_window_width}")
    
    if layout == TilingLayout.HORIZONTAL_SPLIT:
        # Calculate available space after accounting for outer and inner horizontal gaps
        # Outer gaps: left + right = 2 * horizontal_gap
        # Inner gaps: (window_count - 1) * horizontal_gap
        total_gap_space = 2 * horizontal_gap + horizontal_gap * (window_count - 1)
        available_width = container_size.width - total_gap_space
        window_width = available_width // window_count

        # Account for outer vertical gaps: top + bottom = 2 * vertical_gap
        available_height = container_size.height - 2 * vertical_gap
        window_height = available_height

        # Validate minimum sizes
        if window_width < min_window_width or window_height < min_window_height:
            raise ValueError(f"Too many windows for horizontal split: {window_count} windows would result in size {window_width}x{window_height} < {min_window_width}x{min_window_height}")

        for i, window in enumerate(windows):
            x_offset = horizontal_gap + i * (window_width + horizontal_gap)
            y_offset = vertical_gap
            position = Offset(x_offset, y_offset)
            size = Size(window_width, window_height)
            result[window.id] = (position, size)
    
    elif layout == TilingLayout.VERTICAL_SPLIT:
        # Calculate available space after accounting for outer and inner vertical gaps
        # Outer gaps: top + bottom = 2 * vertical_gap
        # Inner gaps: (window_count - 1) * vertical_gap
        total_gap_space = 2 * vertical_gap + vertical_gap * (window_count - 1)
        available_height = container_size.height - total_gap_space
        window_height = available_height // window_count

        # Account for outer horizontal gaps: left + right = 2 * horizontal_gap
        available_width = container_size.width - 2 * horizontal_gap
        window_width = available_width

        # Validate minimum sizes
        if window_width < min_window_width or window_height < min_window_height:
            raise ValueError(f"Too many windows for vertical split: {window_count} windows would result in size {window_width}x{window_height} < {min_window_width}x{min_window_height}")

        for i, window in enumerate(windows):
            x_offset = horizontal_gap
            y_offset = vertical_gap + i * (window_height + vertical_gap)
            position = Offset(x_offset, y_offset)
            size = Size(window_width, window_height)
            result[window.id] = (position, size)
    
    elif layout == TilingLayout.GRID:
        # Arrange in grid pattern
        # Calculate optimal grid dimensions
        cols = math.ceil(math.sqrt(window_count))
        rows = math.ceil(window_count / cols)

        # Calculate available space after accounting for outer and inner gaps
        # Outer gaps: left + right = 2 * horizontal_gap, top + bottom = 2 * vertical_gap
        # Inner gaps: (cols - 1) * horizontal_gap, (rows - 1) * vertical_gap
        total_horizontal_gap_space = 2 * horizontal_gap + horizontal_gap * (cols - 1)
        total_vertical_gap_space = 2 * vertical_gap + vertical_gap * (rows - 1)
        available_width = container_size.width - total_horizontal_gap_space
        available_height = container_size.height - total_vertical_gap_space
        window_width = available_width // cols
        window_height = available_height // rows

        # Validate minimum sizes
        if window_width < min_window_width or window_height < min_window_height:
            raise ValueError(f"Too many windows for grid layout: {window_count} windows would result in size {window_width}x{window_height}, minimum is {min_window_width}x{min_window_height}")

        for i, window in enumerate(windows):
            col = i % cols
            row = i // cols
            x_offset = horizontal_gap + col * (window_width + horizontal_gap)
            y_offset = vertical_gap + row * (window_height + vertical_gap)
            position = Offset(x_offset, y_offset)
            size = Size(window_width, window_height)
            result[window.id] = (position, size)
    
    elif layout == TilingLayout.MASTER_DETAIL:
        # One large master window + smaller detail windows
        if window_count == 1:
            # Single window with outer gaps
            x_offset = horizontal_gap
            y_offset = vertical_gap
            width = container_size.width - 2 * horizontal_gap
            height = container_size.height - 2 * vertical_gap
            position = Offset(x_offset, y_offset)
            size = Size(width, height)
            result[windows[0].id] = (position, size)
        else:
            # Master window takes left 60%, detail windows split right 40%
            # Account for outer gaps and gap between master and detail area
            total_width = container_size.width - 2 * horizontal_gap  # Remove outer gaps
            master_width = int(total_width * 0.6)
            detail_width = total_width - master_width - horizontal_gap  # Gap between master and detail

            # Calculate detail window heights with outer and inner vertical gaps
            detail_count = window_count - 1
            total_detail_gap_space = 2 * vertical_gap + vertical_gap * (detail_count - 1)
            available_detail_height = container_size.height - total_detail_gap_space
            detail_height = available_detail_height // detail_count

            # Validate minimum sizes
            if master_width < min_window_width or detail_width < min_window_width:
                raise ValueError(f"Container too narrow for master-detail layout: master={master_width}, detail={detail_width}, minimum={min_window_width}")
            if detail_height < min_window_height:
                raise ValueError(f"Too many detail windows: {detail_count} detail windows would result in height {detail_height} < {min_window_height}")

            # Master window (first window) - full height with outer gaps
            master_position = Offset(horizontal_gap, vertical_gap)
            master_size = Size(master_width, container_size.height - 2 * vertical_gap)
            result[windows[0].id] = (master_position, master_size)

            # Detail windows (remaining windows)
            for i, window in enumerate(windows[1:], 1):
                detail_x = horizontal_gap + master_width + horizontal_gap
                detail_y = vertical_gap + (i - 1) * (detail_height + vertical_gap)
                detail_position = Offset(detail_x, detail_y)
                detail_size = Size(detail_width, detail_height)
                result[window.id] = (detail_position, detail_size)
    
    else:
        raise ValueError(f"Unsupported tiling layout: {layout}")
    
    return result
