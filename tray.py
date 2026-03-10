"""
VARNA v2.3 - Sunflower Tray UI
A polished, self-contained floating sunflower that expands into a
status panel on click.

Default state:
  - Small sunflower icon floating at the bottom-right of the screen.
  - Always on top, draggable, no title bar.

Expanded state:
  - Sunflower enlarges; a dark card slides open beside it showing
    VARNA v2.3 header, status, recognised speech, command, and result.
  - Click the sunflower again (or the close button) to collapse.

No emojis are used in the UI chrome — all labels are plain text.
Runs in a background thread alongside the main voice loop.
"""

import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

# Try to import pystray — optional dependency
try:
    import pystray
    from PIL import Image, ImageDraw, ImageTk
    _HAS_PYSTRAY = True
except ImportError:
    _HAS_PYSTRAY = False
    log.warning("pystray/Pillow not installed — tray icon disabled. pip install pystray Pillow")


def _resolve_asset(name: str) -> Path:
    """Return the path to an asset file, handling both dev and frozen (PyInstaller) modes."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent / "_internal"
    else:
        base = Path(__file__).parent
    return base / "assets" / name


# ── Colour palette (aligned with the website) ──────────────────────── #
_BG         = "#0d0d20"
_BG_CARD    = "#13132e"
_ACCENT     = "#e94560"
_ACCENT_DIM = "#c73650"
_CYAN       = "#00d2d3"
_GREEN      = "#55efc4"
_TEXT_MAIN  = "#eaeaef"
_TEXT_DIM   = "#8888aa"
_BORDER     = "#2a2a4a"
_SUNFLOWER_SIZE_SMALL  = 52
_SUNFLOWER_SIZE_LARGE  = 72
_CARD_WIDTH            = 300
_CARD_HEIGHT           = 195


class TrayUI:
    """
    Sunflower floating overlay + system tray icon.

    Thread-safe: call update_*() methods from any thread.
    """

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._root: tk.Tk | None = None
        self._tray: "pystray.Icon | None" = None
        self._expanded = False

        # State
        self._status_text = "Listening ..."
        self._last_speech = ""
        self._last_command = ""
        self._last_result = ""

        # Tkinter vars (created on UI thread)
        self._sv_status: tk.StringVar | None = None
        self._sv_speech: tk.StringVar | None = None
        self._sv_command: tk.StringVar | None = None
        self._sv_result: tk.StringVar | None = None

        # Image references (prevent GC)
        self._img_small: "ImageTk.PhotoImage | None" = None
        self._img_large: "ImageTk.PhotoImage | None" = None

        # Widget refs
        self._card_frame: tk.Frame | None = None
        self._sunflower_label: tk.Label | None = None
        self._pulse_after_id: str | None = None

    # ================================================================ #
    # Public API
    # ================================================================ #
    def start(self) -> None:
        """Launch the overlay in a background thread."""
        self._thread = threading.Thread(target=self._run_ui, daemon=True, name="TrayUI")
        self._thread.start()
        log.info("Tray UI thread started.")

    def update_status(self, text: str) -> None:
        self._status_text = text
        if self._root and self._sv_status:
            self._root.after(0, lambda: self._sv_status.set(text))

    def update_speech(self, text: str) -> None:
        self._last_speech = text
        if self._root and self._sv_speech:
            self._root.after(0, lambda: self._sv_speech.set(text))

    def update_command(self, text: str) -> None:
        self._last_command = text
        if self._root and self._sv_command:
            self._root.after(0, lambda: self._sv_command.set(text))

    def update_result(self, text: str) -> None:
        self._last_result = text
        if self._root and self._sv_result:
            self._root.after(0, lambda: self._sv_result.set(text))

    def stop(self) -> None:
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

    # ================================================================ #
    # Build UI
    # ================================================================ #
    def _run_ui(self) -> None:
        self._root = tk.Tk()
        self._root.title("VARNA")
        self._root.attributes("-topmost", True)
        self._root.overrideredirect(True)
        self._root.configure(bg=_BG)
        # Transparent background (Windows-specific)
        self._root.attributes("-transparentcolor", _BG)

        # Load sunflower images
        self._load_images()

        # Position: bottom-right, small initially
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        pad = 24
        init_w = _SUNFLOWER_SIZE_SMALL + 12
        init_h = _SUNFLOWER_SIZE_SMALL + 12
        x = sw - init_w - pad
        y = sh - init_h - 60
        self._root.geometry(f"{init_w}x{init_h}+{x}+{y}")

        # Container frame (transparent)
        self._container = tk.Frame(self._root, bg=_BG)
        self._container.pack(fill=tk.BOTH, expand=True)

        # Sunflower button
        self._sunflower_label = tk.Label(
            self._container,
            image=self._img_small,
            bg=_BG,
            cursor="hand2",
        )
        self._sunflower_label.pack(side=tk.RIGHT, anchor="ne", padx=2, pady=2)
        self._sunflower_label.bind("<Button-1>", self._toggle_expand)
        self._sunflower_label.bind("<Button-3>", self._on_right_click)

        # Dragging on sunflower
        self._sunflower_label.bind("<ButtonPress-1>", self._start_drag, add="+")
        self._sunflower_label.bind("<B1-Motion>", self._do_drag)

        # Build the card (hidden initially)
        self._build_card()

        # Start tray icon
        if _HAS_PYSTRAY:
            threading.Thread(target=self._run_tray, daemon=True).start()

        # Start subtle pulse animation
        self._start_pulse()

        log.info("Sunflower overlay created at (%d, %d)", x, y)
        self._root.mainloop()

    # ─────────────────────────────────────────────────────────────────── #
    def _load_images(self):
        """Load & resize the sunflower PNG for small and large states."""
        try:
            logo_path = _resolve_asset("varna_logo.png")
            pil_img = Image.open(str(logo_path)).convert("RGBA")
            small = pil_img.resize(
                (_SUNFLOWER_SIZE_SMALL, _SUNFLOWER_SIZE_SMALL), Image.LANCZOS
            )
            large = pil_img.resize(
                (_SUNFLOWER_SIZE_LARGE, _SUNFLOWER_SIZE_LARGE), Image.LANCZOS
            )
            self._img_small = ImageTk.PhotoImage(small)
            self._img_large = ImageTk.PhotoImage(large)
        except Exception as exc:
            log.warning("Could not load sunflower image: %s — using fallback", exc)
            self._img_small = None
            self._img_large = None

    # ─────────────────────────────────────────────────────────────────── #
    def _build_card(self):
        """Build the expandable info card (starts hidden)."""
        self._card_frame = tk.Frame(self._container, bg=_BG_CARD, highlightthickness=1,
                                     highlightbackground=_BORDER)
        # Don't pack yet — shown on expand

        # Make card draggable
        self._card_frame.bind("<ButtonPress-1>", self._start_drag)
        self._card_frame.bind("<B1-Motion>", self._do_drag)

        # Inner content with padding
        inner = tk.Frame(self._card_frame, bg=_BG_CARD, padx=16, pady=12)
        inner.pack(fill=tk.BOTH, expand=True)

        # Make inner frame draggable too
        inner.bind("<ButtonPress-1>", self._start_drag)
        inner.bind("<B1-Motion>", self._do_drag)

        # ── Header row ──
        hdr_frame = tk.Frame(inner, bg=_BG_CARD)
        hdr_frame.pack(fill=tk.X)

        tk.Label(
            hdr_frame, text="VARNA", font=("Segoe UI", 16, "bold"),
            fg=_ACCENT, bg=_BG_CARD, anchor="w"
        ).pack(side=tk.LEFT)
        tk.Label(
            hdr_frame, text="v2.3", font=("Segoe UI", 10),
            fg=_TEXT_DIM, bg=_BG_CARD, anchor="w", padx=4
        ).pack(side=tk.LEFT, pady=4)

        # Close button
        close_btn = tk.Label(
            hdr_frame, text="x", font=("Segoe UI", 11, "bold"),
            fg=_TEXT_DIM, bg=_BG_CARD, cursor="hand2", padx=4
        )
        close_btn.pack(side=tk.RIGHT)
        close_btn.bind("<Button-1>", self._toggle_expand)
        close_btn.bind("<Enter>", lambda e: close_btn.config(fg=_ACCENT))
        close_btn.bind("<Leave>", lambda e: close_btn.config(fg=_TEXT_DIM))

        # Accent separator
        tk.Frame(inner, height=2, bg=_ACCENT).pack(fill=tk.X, pady=(6, 10))

        # ── String variables ──
        self._sv_status  = tk.StringVar(value=self._status_text)
        self._sv_speech  = tk.StringVar(value=self._last_speech)
        self._sv_command = tk.StringVar(value=self._last_command)
        self._sv_result  = tk.StringVar(value=self._last_result)

        # ── Status ──
        self._status_dot = tk.Canvas(inner, width=10, height=10, bg=_BG_CARD,
                                      highlightthickness=0)
        status_row = tk.Frame(inner, bg=_BG_CARD)
        status_row.pack(fill=tk.X, pady=(0, 5))
        self._status_dot = tk.Canvas(status_row, width=10, height=10, bg=_BG_CARD,
                                      highlightthickness=0)
        self._status_dot.pack(side=tk.LEFT, padx=(0, 6), pady=4)
        self._status_dot_id = self._status_dot.create_oval(1, 1, 9, 9, fill=_CYAN, outline="")
        tk.Label(
            status_row, textvariable=self._sv_status, font=("Segoe UI", 10),
            fg=_CYAN, bg=_BG_CARD, anchor="w"
        ).pack(side=tk.LEFT, fill=tk.X)

        # ── Recognized speech ──
        self._make_row(inner, "Heard", self._sv_speech, _TEXT_DIM)

        # ── Command ──
        self._make_row(inner, "Command", self._sv_command, _TEXT_MAIN, bold=True)

        # ── Result ──
        self._make_row(inner, "Result", self._sv_result, _GREEN)

    def _make_row(self, parent, label_text: str, var: tk.StringVar, fg: str,
                  bold: bool = False):
        """Create a label + value row inside the card."""
        row = tk.Frame(parent, bg=_BG_CARD)
        row.pack(fill=tk.X, pady=2)
        tk.Label(
            row, text=f"{label_text}:", font=("Segoe UI", 8),
            fg=_TEXT_DIM, bg=_BG_CARD, width=8, anchor="w"
        ).pack(side=tk.LEFT)
        weight = "bold" if bold else "normal"
        tk.Label(
            row, textvariable=var, font=("Segoe UI", 9, weight),
            fg=fg, bg=_BG_CARD, anchor="w", wraplength=220
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

    # ================================================================ #
    # Expand / Collapse
    # ================================================================ #
    def _toggle_expand(self, event=None):
        """Toggle between small sunflower and expanded card."""
        if self._expanded:
            self._collapse()
        else:
            self._expand()

    def _expand(self):
        self._expanded = True

        # Hide sunflower — only the card should be visible
        self._sunflower_label.pack_forget()

        # Show card
        self._card_frame.pack(side=tk.LEFT, padx=4, pady=2, fill=tk.BOTH)

        # Resize window to card only (no sunflower)
        total_w = _CARD_WIDTH + 16
        total_h = _CARD_HEIGHT + 8

        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        x = sw - total_w - 24
        y = sh - total_h - 60
        self._root.geometry(f"{total_w}x{total_h}+{x}+{y}")

        log.debug("Panel expanded (flower hidden)")

    def _collapse(self):
        self._expanded = False

        # Hide card
        self._card_frame.pack_forget()

        # Show sunflower again
        if self._img_small:
            self._sunflower_label.config(image=self._img_small)
        self._sunflower_label.pack(side=tk.RIGHT, anchor="ne", padx=2, pady=2)

        # Resize window back to flower only
        w = _SUNFLOWER_SIZE_SMALL + 12
        h = _SUNFLOWER_SIZE_SMALL + 12
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        x = sw - w - 24
        y = sh - h - 60
        self._root.geometry(f"{w}x{h}+{x}+{y}")

        log.debug("Panel collapsed (flower restored)")

    # ================================================================ #
    # Dragging
    # ================================================================ #
    def _start_drag(self, event):
        self._drag_x = event.x_root - self._root.winfo_x()
        self._drag_y = event.y_root - self._root.winfo_y()
        self._drag_moved = False

    def _do_drag(self, event):
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self._root.geometry(f"+{x}+{y}")
        self._drag_moved = True

    # ================================================================ #
    # Pulse animation (subtle glow on the status dot)
    # ================================================================ #
    def _start_pulse(self):
        """Cycle the status dot colour between cyan and dim."""
        self._pulse_step = 0
        self._pulse()

    def _pulse(self):
        if not self._root:
            return
        self._pulse_step = (self._pulse_step + 1) % 40
        # Simple brightness ramp
        if self._pulse_step < 20:
            ratio = self._pulse_step / 20
        else:
            ratio = (40 - self._pulse_step) / 20
        r = int(0 + ratio * 0)
        g = int(160 + ratio * 50)
        b = int(160 + ratio * 51)
        colour = f"#{r:02x}{g:02x}{b:02x}"
        try:
            if hasattr(self, '_status_dot') and self._status_dot:
                self._status_dot.itemconfig(self._status_dot_id, fill=colour)
        except Exception:
            pass
        self._pulse_after_id = self._root.after(80, self._pulse)

    # ================================================================ #
    # Right-click context menu
    # ================================================================ #
    def _on_right_click(self, event):
        menu = tk.Menu(self._root, tearoff=0, bg=_BG_CARD, fg=_TEXT_MAIN,
                       activebackground=_ACCENT, activeforeground="white",
                       font=("Segoe UI", 9), border=0)
        menu.add_command(label="Show Panel" if not self._expanded else "Hide Panel",
                         command=self._toggle_expand)
        menu.add_separator()
        menu.add_command(label="Exit VARNA", command=self._exit_from_tray)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ================================================================ #
    # System Tray
    # ================================================================ #
    def _run_tray(self) -> None:
        try:
            image = self._load_tray_icon()
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
    def _load_tray_icon() -> "Image.Image":
        """Use the actual sunflower PNG for the tray icon (resized to 64x64)."""
        try:
            logo_path = _resolve_asset("varna_logo.png")
            img = Image.open(str(logo_path)).convert("RGBA")
            return img.resize((64, 64), Image.LANCZOS)
        except Exception:
            # Fallback: draw a simple one
            img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.ellipse([4, 4, 60, 60], fill="#e94560")
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
