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
    container_size: Size
) -> Dict[str, Tuple[Offset, Size]]:
    """Calculate tiling positions and sizes for a list of windows.
    
    This is a pure function that takes window list, layout mode, and container
    size and returns position/size mappings for each window.
    
    Args:
        windows: List of Window objects to arrange
        layout: TilingLayout enum specifying the arrangement mode
        container_size: Size of the container (screen) to arrange windows within
        
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

    window_count = len(windows)
    result: Dict[str, Tuple[Offset, Size]] = {}

    # Ensure minimum window sizes
    min_window_width = 12  # Minimum usable window width
    min_window_height = 6  # Minimum usable window height
    
    if layout == TilingLayout.HORIZONTAL_SPLIT:
        # Divide screen width by window count
        window_width = container_size.width // window_count
        window_height = container_size.height

        # Validate minimum sizes
        if window_width < min_window_width:
            raise ValueError(f"Too many windows for horizontal split: {window_count} windows would result in width {window_width} < {min_window_width}")

        for i, window in enumerate(windows):
            x_offset = i * window_width
            position = Offset(x_offset, 0)
            size = Size(window_width, window_height)
            result[window.id] = (position, size)
    
    elif layout == TilingLayout.VERTICAL_SPLIT:
        # Divide screen height by window count
        window_width = container_size.width
        window_height = container_size.height // window_count

        # Validate minimum sizes
        if window_height < min_window_height:
            raise ValueError(f"Too many windows for vertical split: {window_count} windows would result in height {window_height} < {min_window_height}")

        for i, window in enumerate(windows):
            y_offset = i * window_height
            position = Offset(0, y_offset)
            size = Size(window_width, window_height)
            result[window.id] = (position, size)
    
    elif layout == TilingLayout.GRID:
        # Arrange in grid pattern
        # Calculate optimal grid dimensions
        cols = math.ceil(math.sqrt(window_count))
        rows = math.ceil(window_count / cols)

        window_width = container_size.width // cols
        window_height = container_size.height // rows

        # Validate minimum sizes
        if window_width < min_window_width or window_height < min_window_height:
            raise ValueError(f"Too many windows for grid layout: {window_count} windows would result in size {window_width}x{window_height}, minimum is {min_window_width}x{min_window_height}")

        for i, window in enumerate(windows):
            col = i % cols
            row = i // cols
            x_offset = col * window_width
            y_offset = row * window_height
            position = Offset(x_offset, y_offset)
            size = Size(window_width, window_height)
            result[window.id] = (position, size)
    
    elif layout == TilingLayout.MASTER_DETAIL:
        # One large master window + smaller detail windows
        if window_count == 1:
            # Single window takes full screen
            position = Offset(0, 0)
            size = Size(container_size.width, container_size.height)
            result[windows[0].id] = (position, size)
        else:
            # Master window takes left 60%, detail windows split right 40%
            master_width = int(container_size.width * 0.6)
            detail_width = container_size.width - master_width
            detail_height = container_size.height // (window_count - 1)

            # Validate minimum sizes
            if master_width < min_window_width or detail_width < min_window_width:
                raise ValueError(f"Container too narrow for master-detail layout: master={master_width}, detail={detail_width}, minimum={min_window_width}")
            if detail_height < min_window_height:
                raise ValueError(f"Too many detail windows: {window_count-1} detail windows would result in height {detail_height} < {min_window_height}")

            # Master window (first window)
            master_position = Offset(0, 0)
            master_size = Size(master_width, container_size.height)
            result[windows[0].id] = (master_position, master_size)

            # Detail windows (remaining windows)
            for i, window in enumerate(windows[1:], 1):
                detail_y = (i - 1) * detail_height
                detail_position = Offset(master_width, detail_y)
                detail_size = Size(detail_width, detail_height)
                result[window.id] = (detail_position, detail_size)
    
    else:
        raise ValueError(f"Unsupported tiling layout: {layout}")
    
    return result
