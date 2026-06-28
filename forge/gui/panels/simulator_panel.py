"""
FORGE Simulator Panel — Bottom-right: project render/preview.
Supports mode selection, live render, screenshot capture,
and frame history thumbnail strip.
"""

import customtkinter as ctk
import tkinter as tk
import os
from PIL import Image, ImageTk

import config


class SimulatorPanel(ctk.CTkFrame):
    """
    Right panel bottom — Project render/preview.
    Mode selector, embedded render, screenshot capture, frame history.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.configure(
            fg_color=config.THEME["bg_secondary"],
            corner_radius=0,
        )
        
        self.current_mode = config.DEFAULT_RENDER_MODE
        self.frame_history = []  # List of screenshot paths
        self.on_screenshot = None
        self.on_mode_change = None
        
        # ── Header ───────────────────────────────────────────────
        header = ctk.CTkFrame(
            self, fg_color=config.THEME["bg_tertiary"],
            corner_radius=0, height=36,
        )
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header, text="PROJECT RENDER",
            font=config.FONTS["small"],
            text_color=config.THEME["text_primary"],
        ).pack(side="left", padx=8, pady=6)
        
        # Mode selector
        self.mode_var = ctk.StringVar(value=self.current_mode)
        self.mode_selector = ctk.CTkOptionMenu(
            header,
            values=config.RENDER_MODES,
            variable=self.mode_var,
            command=self._on_mode_changed,
            font=config.FONTS["tiny"],
            fg_color=config.THEME["bg_input"],
            button_color=config.THEME["border"],
            button_hover_color=config.THEME["border_light"],
            dropdown_fg_color=config.THEME["bg_card"],
            dropdown_hover_color=config.THEME["accent"],
            text_color=config.THEME["text_primary"],
            width=100, height=24,
        )
        self.mode_selector.pack(side="left", padx=8, pady=6)
        
        # Screenshot button
        self.capture_btn = ctk.CTkButton(
            header, text="📸 CAP",
            font=config.FONTS["tiny"],
            fg_color=config.THEME["bg_input"],
            hover_color=config.THEME["border_light"],
            text_color=config.THEME["text_primary"],
            width=60, height=24,
            corner_radius=4,
            command=self._capture_screenshot,
        )
        self.capture_btn.pack(side="right", padx=8, pady=6)
        
        # ── Render area ──────────────────────────────────────────
        self.render_frame = ctk.CTkFrame(
            self, fg_color=config.THEME["bg_primary"],
            corner_radius=6,
        )
        self.render_frame.pack(fill="both", expand=True, padx=6, pady=4)
        
        # Canvas for rendering
        self.render_canvas = tk.Canvas(
            self.render_frame,
            bg=config.THEME["bg_primary"],
            highlightthickness=0,
        )
        self.render_canvas.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Default content — show mode info
        self._show_placeholder()
        
        # ── Frame history thumbnail strip ────────────────────────
        self.history_frame = ctk.CTkFrame(
            self, fg_color=config.THEME["bg_tertiary"],
            corner_radius=0, height=60,
        )
        self.history_frame.pack(fill="x", padx=0, pady=(0, 0))
        self.history_frame.pack_propagate(False)
        
        # Scrollable horizontal strip
        self.thumb_container = ctk.CTkFrame(
            self.history_frame, fg_color="transparent",
        )
        self.thumb_container.pack(fill="both", expand=True, padx=4, pady=4)
        
        self.thumbnail_widgets = []
        
        # Status label
        self.status_label = ctk.CTkLabel(
            self.thumb_container,
            text="No frames captured",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
        )
        self.status_label.pack(side="left", padx=8)

    def _show_placeholder(self):
        """Show a placeholder in the render area."""
        self.render_canvas.delete("all")
        w = self.render_canvas.winfo_width() or 300
        h = self.render_canvas.winfo_height() or 200
        
        # Draw a centered display frame
        cx, cy = w // 2, h // 2
        
        # ESP32-style bezel
        if self.current_mode == "esp32":
            # Draw display outline
            dw, dh = 120, 160  # Scaled down for panel
            self.render_canvas.create_rectangle(
                cx - dw//2 - 4, cy - dh//2 - 4,
                cx + dw//2 + 4, cy + dh//2 + 4,
                outline="#333348", width=2, fill="#1A1A24",
            )
            self.render_canvas.create_rectangle(
                cx - dw//2, cy - dh//2,
                cx + dw//2, cy + dh//2,
                outline="#444460", width=1, fill="#000000",
            )
            self.render_canvas.create_text(
                cx, cy,
                text="ESP32\n240×320",
                fill="#4B5563",
                font=("Cascadia Code", 10),
                justify="center",
            )
        else:
            self.render_canvas.create_text(
                cx, cy,
                text=f"Mode: {self.current_mode}\nWaiting for output...",
                fill="#4B5563",
                font=("Segoe UI", 11),
                justify="center",
            )

    def show_image(self, image_path: str):
        """Display an image in the render area."""
        try:
            img = Image.open(image_path)
            
            # Fit to canvas size
            canvas_w = self.render_canvas.winfo_width() or 300
            canvas_h = self.render_canvas.winfo_height() or 200
            
            img.thumbnail((canvas_w - 8, canvas_h - 8), Image.Resampling.LANCZOS)
            
            self._current_photo = ImageTk.PhotoImage(img)
            
            self.render_canvas.delete("all")
            self.render_canvas.create_image(
                canvas_w // 2, canvas_h // 2,
                image=self._current_photo,
                anchor="center",
            )
        except Exception:
            self._show_placeholder()

    def show_terminal_output(self, output: str):
        """Display terminal output in the render area."""
        self.render_canvas.delete("all")
        
        # Green-on-black terminal style
        lines = output.split("\n")[-20:]  # Last 20 lines
        y = 10
        for line in lines:
            self.render_canvas.create_text(
                10, y,
                text=line[:80],
                fill="#4ADE80",
                font=("Cascadia Code", 9),
                anchor="nw",
            )
            y += 14

    def add_frame(self, frame_path: str):
        """Add a frame to the history and display it."""
        if not os.path.exists(frame_path):
            return
        
        self.frame_history.append(frame_path)
        if len(self.frame_history) > 10:
            self.frame_history.pop(0)
        
        # Show the frame
        self.show_image(frame_path)
        
        # Update thumbnail strip
        self._update_thumbnails()

    def _update_thumbnails(self):
        """Update the thumbnail strip with frame history."""
        # Clear existing thumbnails
        for widget in self.thumbnail_widgets:
            widget.destroy()
        self.thumbnail_widgets.clear()
        self.status_label.pack_forget()
        
        if not self.frame_history:
            self.status_label.pack(side="left", padx=8)
            return
        
        for i, path in enumerate(self.frame_history[-10:]):
            try:
                img = Image.open(path)
                img.thumbnail((44, 44), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                
                thumb = tk.Label(
                    self.thumb_container,
                    image=photo,
                    bg=config.THEME["bg_tertiary"],
                    borderwidth=1,
                    relief="solid",
                    cursor="hand2",
                )
                thumb.image = photo  # Keep reference
                thumb.pack(side="left", padx=2)
                thumb.bind("<Button-1>", 
                          lambda e, p=path: self.show_image(p))
                
                self.thumbnail_widgets.append(thumb)
            except Exception:
                pass
        
        # Frame count label
        count_label = ctk.CTkLabel(
            self.thumb_container,
            text=f"{len(self.frame_history)} frames",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
        )
        count_label.pack(side="right", padx=4)
        self.thumbnail_widgets.append(count_label)

    def _on_mode_changed(self, new_mode: str):
        """Handle render mode change."""
        self.current_mode = new_mode
        self._show_placeholder()
        if self.on_mode_change:
            self.on_mode_change(new_mode)

    def _capture_screenshot(self):
        """Trigger a screenshot capture."""
        if self.on_screenshot:
            self.on_screenshot()

    def clear(self):
        """Clear the render display."""
        self.render_canvas.delete("all")
        self._show_placeholder()
