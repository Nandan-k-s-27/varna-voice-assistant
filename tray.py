"""
VARNA v1.3 - System Tray UI
Provides a minimal floating overlay and system tray icon.

Shows:
  • Mic status indicator (🎤 Listening / 🔇 Idle)
  • Last recognised text
  • Last command result
  • Error messages

Runs in a background thread alongside the main voice loop.
"""

import threading
import tkinter as tk
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

# Try to import pystray — optional dependency
try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    _HAS_PYSTRAY = True
except ImportError:
    _HAS_PYSTRAY = False
    log.warning("pystray/Pillow not installed — tray icon disabled. pip install pystray Pillow")


class TrayUI:
    """
    Minimal floating overlay + system tray icon.

    Thread-safe: call update_*() methods from any thread.
    """

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._root: tk.Tk | None = None
        self._tray: "pystray.Icon | None" = None

        # State (thread-safe via tkinter's after())
        self._status_text = "🎤 Listening …"
        self._last_speech = ""
        self._last_command = ""
        self._last_result = ""

        # Tkinter string vars (created on UI thread)
        self._sv_status: tk.StringVar | None = None
        self._sv_speech: tk.StringVar | None = None
        self._sv_command: tk.StringVar | None = None
        self._sv_result: tk.StringVar | None = None

    # ------------------------------------------------------------------ #
    def start(self) -> None:
        """Launch the overlay in a background thread."""
        self._thread = threading.Thread(target=self._run_ui, daemon=True, name="TrayUI")
        self._thread.start()
        log.info("Tray UI thread started.")

    # ------------------------------------------------------------------ #
    def _run_ui(self) -> None:
        """Build and run the tkinter overlay (runs in its own thread)."""
        self._root = tk.Tk()
        self._root.title("VARNA")
        self._root.attributes("-topmost", True)
        self._root.overrideredirect(True)  # No title bar
        self._root.configure(bg="#1a1a2e")

        # Position: bottom-right corner
        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        win_w, win_h = 340, 180
        x = screen_w - win_w - 20
        y = screen_h - win_h - 60
        self._root.geometry(f"{win_w}x{win_h}+{x}+{y}")

        # Rounded feel with padding
        frame = tk.Frame(self._root, bg="#1a1a2e", padx=14, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header = tk.Label(
            frame, text="🎙 VARNA v1.3", font=("Segoe UI", 13, "bold"),
            fg="#e94560", bg="#1a1a2e", anchor="w",
        )
        header.pack(fill=tk.X)

        # Separator
        sep = tk.Frame(frame, height=1, bg="#e94560")
        sep.pack(fill=tk.X, pady=(4, 6))

        # String variables
        self._sv_status = tk.StringVar(value=self._status_text)
        self._sv_speech = tk.StringVar(value=self._last_speech)
        self._sv_command = tk.StringVar(value=self._last_command)
        self._sv_result = tk.StringVar(value=self._last_result)

        # Status row
        tk.Label(
            frame, textvariable=self._sv_status, font=("Segoe UI", 10),
            fg="#00d2d3", bg="#1a1a2e", anchor="w",
        ).pack(fill=tk.X)

        # Speech row
        tk.Label(
            frame, textvariable=self._sv_speech, font=("Segoe UI", 9),
            fg="#a0a0b0", bg="#1a1a2e", anchor="w",
        ).pack(fill=tk.X, pady=(2, 0))

        # Command row
        tk.Label(
            frame, textvariable=self._sv_command, font=("Segoe UI", 10, "bold"),
            fg="#ffffff", bg="#1a1a2e", anchor="w",
        ).pack(fill=tk.X, pady=(2, 0))

        # Result row
        tk.Label(
            frame, textvariable=self._sv_result, font=("Segoe UI", 9),
            fg="#55efc4", bg="#1a1a2e", anchor="w",
        ).pack(fill=tk.X, pady=(2, 0))

        # Make window draggable
        self._root.bind("<Button-1>", self._start_drag)
        self._root.bind("<B1-Motion>", self._do_drag)

        # Start tray icon if available
        if _HAS_PYSTRAY:
            tray_thread = threading.Thread(target=self._run_tray, daemon=True)
            tray_thread.start()

        log.info("Overlay window created at (%d, %d)", x, y)
        self._root.mainloop()

    # ------------------------------------------------------------------ #
    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _do_drag(self, event):
        x = self._root.winfo_x() + event.x - self._drag_x
        y = self._root.winfo_y() + event.y - self._drag_y
        self._root.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------ #
    def _run_tray(self) -> None:
        """Create a system tray icon."""
        try:
            image = self._create_tray_icon()
            menu = pystray.Menu(
                pystray.MenuItem("Show", self._show_overlay),
                pystray.MenuItem("Hide", self._hide_overlay),
                pystray.MenuItem("Exit", self._exit_from_tray),
            )
            self._tray = pystray.Icon("VARNA", image, "VARNA Voice Assistant", menu)
            self._tray.run()
        except Exception as exc:
            log.error("Tray icon failed: %s", exc)

    @staticmethod
    def _create_tray_icon() -> "Image.Image":
        """Generate a simple red-circle mic icon."""
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Red circle
        draw.ellipse([4, 4, 60, 60], fill="#e94560")
        # White mic shape (simple rectangle + circle)
        draw.rectangle([26, 14, 38, 38], fill="white")
        draw.ellipse([22, 30, 42, 46], fill="white")
        draw.rectangle([30, 44, 34, 54], fill="white")
        draw.line([22, 54, 42, 54], fill="white", width=2)
        return img

    def _show_overlay(self, *_):
        if self._root:
            self._root.after(0, self._root.deiconify)

    def _hide_overlay(self, *_):
        if self._root:
            self._root.after(0, self._root.withdraw)

    def _exit_from_tray(self, *_):
        if self._tray:
            self._tray.stop()
        if self._root:
            self._root.after(0, self._root.destroy)

    # ------------------------------------------------------------------ #
    # Thread-safe update methods (called from main thread)
    # ------------------------------------------------------------------ #
    def update_status(self, text: str) -> None:
        """Update the mic/status indicator."""
        self._status_text = text
        if self._root and self._sv_status:
            self._root.after(0, lambda: self._sv_status.set(text))

    def update_speech(self, text: str) -> None:
        """Update the last recognised speech text."""
        self._last_speech = f'🗣 "{text}"'
        if self._root and self._sv_speech:
            val = self._last_speech
            self._root.after(0, lambda: self._sv_speech.set(val))

    def update_command(self, text: str) -> None:
        """Update the last matched command."""
        self._last_command = f"▶ {text}"
        if self._root and self._sv_command:
            val = self._last_command
            self._root.after(0, lambda: self._sv_command.set(val))

    def update_result(self, text: str) -> None:
        """Update the last result/status."""
        self._last_result = text
        if self._root and self._sv_result:
            val = text
            self._root.after(0, lambda: self._sv_result.set(val))

    def stop(self) -> None:
        """Shut down the overlay and tray."""
        if self._tray:
            try:
                self._tray.stop()
            except Exception:
                pass
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass
        log.info("Tray UI stopped.")
