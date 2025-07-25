"""Demo script to test the tiling window manager functionality."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Static, Button
from textual.containers import Container, Horizontal

from textual_window import Window, window_manager, TilingLayout


class TilingDemo(App[None]):
    """Demo app to test tiling functionality."""
    
    CSS = """
    Screen {
        background: $background;
    }
    
    #main_container {
        width: 100%;
        height: 100%;
    }
    
    #controls {
        dock: top;
        height: 3;
        background: $panel;
        padding: 1;
    }
    
    Button {
        margin: 0 1;
    }
    """
    
    # Add tiling keybindings to the main app
    BINDINGS = [
        Binding("ctrl+shift+f", "toggle_tiling", "Toggle Tiling"),
        Binding("ctrl+shift+h", "set_horizontal_split", "Horizontal Split"),
        Binding("ctrl+shift+v", "set_vertical_split", "Vertical Split"),
        Binding("ctrl+shift+g", "set_grid_layout", "Grid Layout"),
        Binding("ctrl+shift+m", "set_master_detail", "Master Detail"),
        Binding("ctrl+shift+t", "cycle_tiling_mode", "Cycle Tiling Mode"),
        Binding("ctrl+n", "add_window", "Add Window"),
        Binding("ctrl+q", "quit", "Quit"),
    ]
    
    def __init__(self):
        super().__init__()
        self.title = "Tiling Window Manager Demo"
        self.window_counter = 1
    
    def compose(self) -> ComposeResult:
        with Container(id="main_container"):
            # Control panel
            with Horizontal(id="controls"):
                yield Button("Add Window", id="add_window")
                yield Button("Horizontal", id="horizontal")
                yield Button("Vertical", id="vertical")
                yield Button("Grid", id="grid")
                yield Button("Master-Detail", id="master_detail")
                yield Button("Floating", id="floating")
            
            # Initial windows
            yield Window(
                Static("Window 1\nUse Ctrl+Shift+H/V/G/M/F for tiling\nOr click buttons above"),
                id="window_1",
                start_open=True,
                starting_horizontal="left",
                starting_vertical="top",
            )
            
            yield Window(
                Static("Window 2\nTry adding more windows\nwith Ctrl+N or Add Window button"),
                id="window_2", 
                start_open=True,
                starting_horizontal="right",
                starting_vertical="top",
            )
    
    # Tiling action methods
    def action_toggle_tiling(self) -> None:
        """Toggle between floating and horizontal split."""
        if window_manager.tiling_layout == TilingLayout.FLOATING:
            window_manager.set_tiling_layout(TilingLayout.HORIZONTAL_SPLIT)
            self.notify("Tiling: Horizontal Split")
        else:
            window_manager.set_tiling_layout(TilingLayout.FLOATING)
            self.notify("Tiling: Floating")
    
    def action_set_horizontal_split(self) -> None:
        """Set horizontal split tiling."""
        window_manager.set_tiling_layout(TilingLayout.HORIZONTAL_SPLIT)
        self.notify("Tiling: Horizontal Split")
    
    def action_set_vertical_split(self) -> None:
        """Set vertical split tiling."""
        window_manager.set_tiling_layout(TilingLayout.VERTICAL_SPLIT)
        self.notify("Tiling: Vertical Split")
    
    def action_set_grid_layout(self) -> None:
        """Set grid tiling."""
        window_manager.set_tiling_layout(TilingLayout.GRID)
        self.notify("Tiling: Grid Layout")
    
    def action_set_master_detail(self) -> None:
        """Set master-detail tiling."""
        window_manager.set_tiling_layout(TilingLayout.MASTER_DETAIL)
        self.notify("Tiling: Master-Detail")
    
    def action_cycle_tiling_mode(self) -> None:
        """Cycle through all tiling modes."""
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
        self.notify(f"Tiling: {new_mode.value.replace('_', ' ').title()}")
    
    def action_add_window(self) -> None:
        """Add a new window."""
        self.window_counter += 1
        new_window = Window(
            Static(f"Window {self.window_counter}\nDynamically added\nCurrent mode: {window_manager.tiling_layout.value}"),
            id=f"window_{self.window_counter}",
            start_open=True,
        )
        self.query_one("#main_container").mount(new_window)
        self.notify(f"Added Window {self.window_counter}")
    
    # Button event handlers
    def on_button_pressed(self, event) -> None:
        """Handle button presses."""
        button_id = event.button.id
        
        if button_id == "add_window":
            self.action_add_window()
        elif button_id == "horizontal":
            self.action_set_horizontal_split()
        elif button_id == "vertical":
            self.action_set_vertical_split()
        elif button_id == "grid":
            self.action_set_grid_layout()
        elif button_id == "master_detail":
            self.action_set_master_detail()
        elif button_id == "floating":
            window_manager.set_tiling_layout(TilingLayout.FLOATING)
            self.notify("Tiling: Floating")


if __name__ == "__main__":
    app = TilingDemo()
    app.run()
