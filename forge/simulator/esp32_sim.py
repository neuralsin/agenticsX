"""
FORGE ESP32 Simulator — ESP32/ILI9341 specific renderer (240x320).
Provides a pygame-based display simulation at 3x scale.
"""

import os
import threading


class ESP32Simulator:
    """
    ESP32/ILI9341 display simulator.
    240x320 pixel display rendered at 3x scale (720x960 window).
    """

    DISPLAY_WIDTH = 240
    DISPLAY_HEIGHT = 320
    SCALE = 3

    def __init__(self):
        self._surface = None
        self._display_surface = None
        self._running = False
        self._pygame = None

    def start(self):
        """Initialize the pygame display."""
        try:
            import pygame
            self._pygame = pygame
            pygame.init()
            
            window_w = self.DISPLAY_WIDTH * self.SCALE
            window_h = self.DISPLAY_HEIGHT * self.SCALE
            
            self._surface = pygame.display.set_mode((window_w, window_h))
            pygame.display.set_caption("FORGE — ESP32 ILI9341 Simulator")
            
            # Create the actual display surface at native resolution
            self._display_surface = pygame.Surface(
                (self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT)
            )
            self._display_surface.fill((0, 0, 0))
            
            self._running = True
            self._update_display()
        except ImportError:
            pass

    def stop(self):
        """Shut down the pygame display."""
        self._running = False
        if self._pygame:
            try:
                self._pygame.quit()
            except Exception:
                pass

    def render_frame(self, draw_callback):
        """
        Render a frame using the provided draw callback.
        draw_callback receives the native-resolution pygame Surface (240x320).
        """
        if not self._display_surface or not self._pygame:
            return

        self._display_surface.fill((0, 0, 0))
        draw_callback(self._display_surface)
        self._update_display()

    def fill_color(self, r: int, g: int, b: int):
        """Fill the display with a solid color."""
        if self._display_surface:
            self._display_surface.fill((r, g, b))
            self._update_display()

    def draw_pixel(self, x: int, y: int, color: tuple):
        """Draw a single pixel on the display."""
        if self._display_surface and 0 <= x < self.DISPLAY_WIDTH \
                and 0 <= y < self.DISPLAY_HEIGHT:
            self._display_surface.set_at((x, y), color)

    def draw_rect(self, x: int, y: int, w: int, h: int, color: tuple):
        """Draw a filled rectangle."""
        if self._display_surface and self._pygame:
            self._pygame.draw.rect(
                self._display_surface, color,
                (x, y, w, h)
            )

    def draw_text(self, text: str, x: int, y: int, color: tuple = (255, 255, 255),
                  size: int = 16):
        """Draw text on the display."""
        if not self._display_surface or not self._pygame:
            return
        try:
            font = self._pygame.font.SysFont("monospace", size)
            text_surface = font.render(text, True, color)
            self._display_surface.blit(text_surface, (x, y))
        except Exception:
            pass

    def screenshot(self, path: str):
        """Save current display to file."""
        if self._surface and self._pygame:
            try:
                self._pygame.image.save(self._surface, path)
            except Exception:
                pass

    def _update_display(self):
        """Scale and blit the display surface to the window."""
        if self._surface and self._display_surface and self._pygame:
            scaled = self._pygame.transform.scale(
                self._display_surface,
                (self.DISPLAY_WIDTH * self.SCALE, 
                 self.DISPLAY_HEIGHT * self.SCALE)
            )
            self._surface.blit(scaled, (0, 0))
            self._pygame.display.flip()

    def process_events(self) -> bool:
        """Process pygame events. Returns False if window was closed."""
        if not self._pygame:
            return True
        for event in self._pygame.event.get():
            if event.type == self._pygame.QUIT:
                self._running = False
                return False
        return True

    @property
    def is_running(self) -> bool:
        return self._running
