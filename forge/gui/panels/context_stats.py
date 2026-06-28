"""
FORGE Context Stats Panel — Bottom bar: token usage, RAM, VRAM meters.
Shows per-agent token meters, DB size, RAM/VRAM usage, iteration counter.
"""

import customtkinter as ctk
import tkinter as tk

from gui.widgets.token_meter import TokenMeter
import config


class ContextStatsPanel(ctk.CTkFrame):
    """
    Bottom bar showing comprehensive stats:
    - Per-agent token meters (colored bars)
    - DB size counter
    - RAM usage (psutil)
    - VRAM usage (pynvml)
    - Iteration counter
    - Total tokens used
    - Estimated cost
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.configure(
            fg_color=config.THEME["bg_tertiary"],
            corner_radius=0,
            height=70,
        )
        self.pack_propagate(False)
        
        # ── Row 1: Plan progress ─────────────────────────────────
        progress_row = ctk.CTkFrame(self, fg_color="transparent", height=28)
        progress_row.pack(fill="x", padx=12, pady=(4, 0))
        progress_row.pack_propagate(False)
        
        ctk.CTkLabel(
            progress_row, text="PLAN PROGRESS",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
        ).pack(side="left")
        
        self.plan_progress = ctk.CTkProgressBar(
            progress_row, height=8,
            corner_radius=4,
            progress_color=config.THEME["accent"],
            fg_color=config.THEME["bg_primary"],
            width=200,
        )
        self.plan_progress.pack(side="left", padx=8)
        self.plan_progress.set(0)
        
        self.plan_label = ctk.CTkLabel(
            progress_row, text="Step 0 of 0",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_secondary"],
        )
        self.plan_label.pack(side="left", padx=4)
        
        # Step indicator dots
        self.step_dots = ctk.CTkLabel(
            progress_row, text="",
            font=("Segoe UI", 9),
            text_color=config.THEME["text_muted"],
        )
        self.step_dots.pack(side="left", padx=8)
        
        # Right side: iteration counter
        self.iter_label = ctk.CTkLabel(
            progress_row, text="Iter: 0/50",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
        )
        self.iter_label.pack(side="right")
        
        # ── Row 2: Token meters + system stats ───────────────────
        stats_row = ctk.CTkFrame(self, fg_color="transparent", height=28)
        stats_row.pack(fill="x", padx=12, pady=(2, 4))
        stats_row.grid_columnconfigure(0, weight=1)
        stats_row.grid_columnconfigure(1, weight=1)
        stats_row.grid_columnconfigure(2, weight=1)
        stats_row.grid_columnconfigure(3, weight=1)
        stats_row.grid_columnconfigure(4, weight=1)
        stats_row.grid_columnconfigure(5, weight=0)
        
        # Token meters for each agent
        self.token_meters = {}
        agents = ["SUPERVISOR", "PLANNER", "CODER", "DEBUGGER", "VISION"]
        
        for i, agent in enumerate(agents):
            meter = TokenMeter(
                stats_row, agent,
                max_tokens=config.CONTEXT_BUDGETS.get(agent, 4096),
            )
            meter.grid(row=0, column=i, sticky="ew", padx=2)
            self.token_meters[agent] = meter
        
        # System stats (right side)
        sys_frame = ctk.CTkFrame(stats_row, fg_color="transparent")
        sys_frame.grid(row=0, column=5, padx=(12, 0))
        
        self.db_label = ctk.CTkLabel(
            sys_frame, text="DB: 0.0MB",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
        )
        self.db_label.pack(side="left", padx=4)
        
        self.ram_label = ctk.CTkLabel(
            sys_frame, text="RAM: --",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
        )
        self.ram_label.pack(side="left", padx=4)
        
        self.vram_label = ctk.CTkLabel(
            sys_frame, text="VRAM: --",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
        )
        self.vram_label.pack(side="left", padx=4)
        
        self.total_tokens_label = ctk.CTkLabel(
            sys_frame, text="Total: 0",
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_secondary"],
        )
        self.total_tokens_label.pack(side="left", padx=4)
        
        self.cost_label = ctk.CTkLabel(
            sys_frame, text="$0.00 — Local",
            font=config.FONTS["tiny"],
            text_color=config.THEME["success"],
        )
        self.cost_label.pack(side="left", padx=4)
        
        # Start periodic hardware monitoring
        self._update_hardware_stats()

    def update_stats(self, stats: dict):
        """Update all stats from an AgentManager stats dict."""
        # Update per-agent token meters
        per_agent = stats.get("per_agent", {})
        for agent_name, agent_stats in per_agent.items():
            if agent_name in self.token_meters:
                self.token_meters[agent_name].update_value(
                    agent_stats.get("tokens_total", 0)
                )
        
        # Update plan progress
        current_step = stats.get("current_step", 0)
        total_steps = stats.get("total_steps", 0)
        
        if total_steps > 0:
            self.plan_progress.set(current_step / total_steps)
            self.plan_label.configure(
                text=f"Step {current_step} of {total_steps}"
            )
            # Generate step dots
            dots = ""
            for i in range(total_steps):
                if i < current_step:
                    dots += "✓"
                elif i == current_step:
                    dots += "→"
                else:
                    dots += "○"
            self.step_dots.configure(text=dots[:20])  # Limit display
        
        # Update iteration counter
        iteration = stats.get("iteration", 0)
        max_iter = stats.get("max_iterations", config.MAX_ITERATIONS)
        self.iter_label.configure(text=f"Iter: {iteration}/{max_iter}")
        
        # Update totals
        total = stats.get("total_tokens", 0)
        if total >= 1000:
            total_text = f"Total: {total/1000:.1f}K"
        else:
            total_text = f"Total: {total}"
        self.total_tokens_label.configure(text=total_text)
        
        # Update DB size
        db_size = stats.get("db_size_mb", 0)
        self.db_label.configure(text=f"DB: {db_size:.1f}MB")

    def update_plan(self, plan: list, current_step: int):
        """Update plan progress display."""
        total = len(plan)
        if total > 0:
            self.plan_progress.set(current_step / total)
            self.plan_label.configure(
                text=f"Step {current_step} of {total}"
            )

    def _update_hardware_stats(self):
        """Periodically update RAM and VRAM usage."""
        try:
            import psutil
            ram = psutil.virtual_memory()
            ram_used_gb = ram.used / (1024**3)
            ram_total_gb = ram.total / (1024**3)
            ram_pct = ram.percent
            self.ram_label.configure(
                text=f"RAM: {ram_used_gb:.1f}/{ram_total_gb:.0f}GB"
            )
            # Color based on usage
            if ram_pct > 90:
                self.ram_label.configure(text_color=config.THEME["error"])
            elif ram_pct > 75:
                self.ram_label.configure(text_color=config.THEME["warning"])
            else:
                self.ram_label.configure(text_color=config.THEME["text_muted"])
        except ImportError:
            self.ram_label.configure(text="RAM: N/A")
        
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            vram_used_gb = mem_info.used / (1024**3)
            vram_total_gb = mem_info.total / (1024**3)
            vram_pct = (mem_info.used / mem_info.total) * 100
            self.vram_label.configure(
                text=f"VRAM: {vram_used_gb:.1f}/{vram_total_gb:.0f}GB"
            )
            if vram_pct > 90:
                self.vram_label.configure(text_color=config.THEME["error"])
            elif vram_pct > 75:
                self.vram_label.configure(text_color=config.THEME["warning"])
            else:
                self.vram_label.configure(text_color=config.THEME["text_muted"])
            pynvml.nvmlShutdown()
        except Exception:
            self.vram_label.configure(text="VRAM: N/A")
        
        # Schedule next update (every 5 seconds)
        self.after(5000, self._update_hardware_stats)
