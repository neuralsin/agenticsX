"""
FORGE Diagnostics Dialog — Full system health check panel.
Tests all models, checks hardware, validates storage, tests network.
"""

import customtkinter as ctk
import threading
import time
import os

import config


class DiagnosticsDialog(ctk.CTkToplevel):
    """
    Full diagnostics dialog with model health checks, hardware stats,
    storage validation, and network connectivity tests.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self.title("FORGE — System Diagnostics")
        self.geometry("680x720")
        self.minsize(580, 600)
        self.configure(fg_color=config.THEME["bg_secondary"])
        self.transient(parent)
        self.grab_set()

        self._checks = {}  # name -> {status, message, widget}

        self._build_ui()

    def _build_ui(self):
        """Build the diagnostics UI."""
        # Header
        header = ctk.CTkFrame(
            self, fg_color=config.THEME["bg_tertiary"],
            corner_radius=0, height=50,
        )
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="🔧 System Diagnostics",
            font=config.FONTS["heading"],
            text_color=config.THEME["text_primary"],
        ).pack(side="left", padx=16, pady=10)

        ctk.CTkButton(
            header, text="▶ Run All Checks",
            font=config.FONTS["small"],
            fg_color=config.THEME["accent"],
            hover_color=config.THEME["accent_hover"],
            text_color="#FFFFFF",
            width=130, height=30,
            corner_radius=6,
            command=self._run_all_checks,
        ).pack(side="right", padx=16, pady=10)

        # Scrollable content
        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
        )
        self.scroll.pack(fill="both", expand=True, padx=12, pady=8)

        # ── Section: Models ──────────────────────────────────────
        self._add_section("Model Health")
        self._add_check("ollama_service", "Ollama Service",
                        "Check if Ollama daemon is running")
        self._add_check("ollama_planner", f"Planner Model ({config.OLLAMA_PLANNER_MODEL})",
                        "Verify model is pulled and responsive")
        self._add_check("ollama_debugger", f"Debugger Model ({config.OLLAMA_DEBUGGER_MODEL})",
                        "Verify model is pulled and responsive")
        self._add_check("ollama_vision", f"Vision Model ({config.OLLAMA_VISION_MODEL})",
                        "Verify multimodal model is available")
        self._add_check("airllm_deps", "AirLLM Dependencies",
                        "Check PyTorch + AirLLM installation")
        self._add_check("gemini_api", "Gemini API (AUDITOR)",
                        "Test API key and connectivity")

        # ── Section: Hardware ────────────────────────────────────
        self._add_section("Hardware")
        self._add_check("gpu_vram", "GPU VRAM",
                        "Check available GPU memory")
        self._add_check("system_ram", "System RAM",
                        "Check available system memory")
        self._add_check("cpu_info", "CPU",
                        "Processor information")
        self._add_check("disk_space", "Disk Space",
                        "Check available disk space")

        # ── Section: Storage ─────────────────────────────────────
        self._add_section("Storage & Data")
        self._add_check("sqlite_db", "Context Database (SQLite)",
                        "Verify database integrity")
        self._add_check("rag_index", "RAG Documentation Index",
                        "Check indexed documentation files")
        self._add_check("git_available", "Git (Time Travel)",
                        "Check git installation")
        self._add_check("pytest_available", "pytest (TDD)",
                        "Check test framework")

        # ── Section: Network ─────────────────────────────────────
        self._add_section("Network")
        self._add_check("ollama_network", "Ollama Connection",
                        f"Connect to {config.OLLAMA_HOST}")
        self._add_check("gemini_network", "Gemini API Reachability",
                        "Connect to Google AI API")

        # Close button
        ctk.CTkButton(
            self, text="Close",
            font=config.FONTS["body"],
            fg_color=config.THEME["bg_input"],
            hover_color=config.THEME["border_light"],
            text_color=config.THEME["text_primary"],
            width=100, height=36,
            corner_radius=8,
            command=self.destroy,
        ).pack(pady=(4, 12))

    def _add_section(self, title: str):
        """Add a section header."""
        ctk.CTkLabel(
            self.scroll, text=title.upper(),
            font=config.FONTS["label_caps"],
            text_color=config.THEME["accent"],
        ).pack(anchor="w", padx=4, pady=(12, 4))

        ctk.CTkFrame(
            self.scroll, fg_color=config.THEME["border"],
            height=1, corner_radius=0,
        ).pack(fill="x", pady=(0, 4))

    def _add_check(self, check_id: str, title: str, description: str):
        """Add a diagnostic check row."""
        row = ctk.CTkFrame(
            self.scroll, fg_color=config.THEME["bg_card"],
            corner_radius=6, height=52,
        )
        row.pack(fill="x", pady=2)
        row.pack_propagate(False)

        # Status indicator
        status_label = ctk.CTkLabel(
            row, text="⏳",
            font=("Segoe UI", 14),
            width=30,
        )
        status_label.pack(side="left", padx=(8, 4))

        # Title + description
        text_frame = ctk.CTkFrame(row, fg_color="transparent")
        text_frame.pack(side="left", fill="x", expand=True, padx=4)

        ctk.CTkLabel(
            text_frame, text=title,
            font=config.FONTS["small"],
            text_color=config.THEME["text_primary"],
            anchor="w",
        ).pack(anchor="w")

        msg_label = ctk.CTkLabel(
            text_frame, text=description,
            font=config.FONTS["tiny"],
            text_color=config.THEME["text_muted"],
            anchor="w",
        )
        msg_label.pack(anchor="w")

        # Re-run button
        ctk.CTkButton(
            row, text="↻",
            font=("Segoe UI", 12),
            fg_color="transparent",
            hover_color=config.THEME["bg_input"],
            text_color=config.THEME["text_secondary"],
            width=28, height=28,
            corner_radius=4,
            command=lambda cid=check_id: self._run_single_check(cid),
        ).pack(side="right", padx=8)

        self._checks[check_id] = {
            "status": "pending",
            "message": description,
            "status_label": status_label,
            "msg_label": msg_label,
        }

    def _update_check(self, check_id: str, passed: bool, message: str):
        """Update a check's status (thread-safe)."""
        def do_update():
            if check_id not in self._checks:
                return
            check = self._checks[check_id]
            check["status"] = "pass" if passed else "fail"
            check["message"] = message
            check["status_label"].configure(
                text="✅" if passed else "❌"
            )
            check["msg_label"].configure(
                text=message,
                text_color=(
                    config.THEME["success"] if passed
                    else config.THEME["error"]
                ),
            )

        self.after(0, do_update)

    def _run_all_checks(self):
        """Run all diagnostic checks in a background thread."""
        # Reset all to pending
        for check_id, check in self._checks.items():
            check["status_label"].configure(text="⏳")
            check["msg_label"].configure(
                text="Checking...",
                text_color=config.THEME["text_muted"],
            )

        threading.Thread(
            target=self._execute_all_checks, daemon=True
        ).start()

    def _run_single_check(self, check_id: str):
        """Run a single check."""
        check = self._checks.get(check_id)
        if check:
            check["status_label"].configure(text="⏳")
            check["msg_label"].configure(
                text="Checking...",
                text_color=config.THEME["text_muted"],
            )
        threading.Thread(
            target=self._execute_check, args=(check_id,), daemon=True
        ).start()

    def _execute_all_checks(self):
        """Execute all checks sequentially."""
        for check_id in self._checks:
            self._execute_check(check_id)
            time.sleep(0.1)  # Small delay for UI updates

    def _execute_check(self, check_id: str):
        """Execute a single diagnostic check."""
        try:
            if check_id == "ollama_service":
                self._check_ollama_service()
            elif check_id == "ollama_planner":
                self._check_ollama_model(config.OLLAMA_PLANNER_MODEL, check_id)
            elif check_id == "ollama_debugger":
                self._check_ollama_model(config.OLLAMA_DEBUGGER_MODEL, check_id)
            elif check_id == "ollama_vision":
                self._check_ollama_model(config.OLLAMA_VISION_MODEL, check_id)
            elif check_id == "airllm_deps":
                self._check_airllm()
            elif check_id == "gemini_api":
                self._check_gemini()
            elif check_id == "gpu_vram":
                self._check_gpu()
            elif check_id == "system_ram":
                self._check_ram()
            elif check_id == "cpu_info":
                self._check_cpu()
            elif check_id == "disk_space":
                self._check_disk()
            elif check_id == "sqlite_db":
                self._check_sqlite()
            elif check_id == "rag_index":
                self._check_rag()
            elif check_id == "git_available":
                self._check_git()
            elif check_id == "pytest_available":
                self._check_pytest()
            elif check_id == "ollama_network":
                self._check_ollama_network()
            elif check_id == "gemini_network":
                self._check_gemini_network()
        except Exception as e:
            self._update_check(check_id, False, f"Check error: {str(e)}")

    # ── Individual check implementations ──────────────────────────

    def _check_ollama_service(self):
        from agents.ollama_agent import OllamaAgent
        ok, msg = OllamaAgent.check_ollama_available()
        self._update_check("ollama_service", ok, msg)

    def _check_ollama_model(self, model_name: str, check_id: str):
        from agents.ollama_agent import OllamaAgent
        ok, msg = OllamaAgent.check_model_available(model_name)
        self._update_check(check_id, ok, msg)

    def _check_airllm(self):
        try:
            import torch
            cuda = torch.cuda.is_available()
            if cuda:
                device = torch.cuda.get_device_name(0)
                self._update_check("airllm_deps", True,
                                   f"PyTorch + CUDA OK — {device}")
            else:
                self._update_check("airllm_deps", False,
                                   "PyTorch installed but CUDA not available")
        except ImportError:
            self._update_check("airllm_deps", False,
                               "PyTorch not installed — pip install torch")

    def _check_gemini(self):
        if not config.GEMINI_API_KEY:
            self._update_check("gemini_api", False,
                               "GEMINI_API_KEY not set")
            return
        try:
            from agents.auditor import AuditorAgent
            ok, msg = AuditorAgent.check_api_available()
            self._update_check("gemini_api", ok, msg)
        except Exception as e:
            self._update_check("gemini_api", False, str(e))

    def _check_gpu(self):
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")
            total_gb = info.total / (1024 ** 3)
            used_gb = info.used / (1024 ** 3)
            free_gb = info.free / (1024 ** 3)
            self._update_check("gpu_vram", True,
                               f"{name} — {used_gb:.1f}/{total_gb:.1f}GB used, "
                               f"{free_gb:.1f}GB free")
            pynvml.nvmlShutdown()
        except ImportError:
            self._update_check("gpu_vram", False,
                               "pynvml not installed — pip install pynvml")
        except Exception as e:
            self._update_check("gpu_vram", False, f"GPU check failed: {e}")

    def _check_ram(self):
        try:
            import psutil
            mem = psutil.virtual_memory()
            total_gb = mem.total / (1024 ** 3)
            avail_gb = mem.available / (1024 ** 3)
            used_pct = mem.percent
            ok = avail_gb > 2.0
            self._update_check("system_ram", ok,
                               f"{avail_gb:.1f}GB free / {total_gb:.1f}GB total "
                               f"({used_pct}% used)")
        except ImportError:
            self._update_check("system_ram", False,
                               "psutil not installed")

    def _check_cpu(self):
        try:
            import psutil
            cpu_pct = psutil.cpu_percent(interval=0.5)
            cores = psutil.cpu_count(logical=True)
            freq = psutil.cpu_freq()
            freq_str = f"{freq.current:.0f}MHz" if freq else "N/A"
            self._update_check("cpu_info", True,
                               f"{cores} cores @ {freq_str} — {cpu_pct}% usage")
        except Exception:
            import platform
            self._update_check("cpu_info", True, platform.processor())

    def _check_disk(self):
        try:
            import psutil
            usage = psutil.disk_usage(str(config.FORGE_DIR))
            free_gb = usage.free / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            ok = free_gb > 10.0
            self._update_check("disk_space", ok,
                               f"{free_gb:.1f}GB free / {total_gb:.0f}GB total")
        except Exception as e:
            self._update_check("disk_space", False, str(e))

    def _check_sqlite(self):
        db_path = str(config.STORAGE_DIR / "context.db")
        if os.path.exists(db_path):
            size_mb = os.path.getsize(db_path) / (1024 * 1024)
            self._update_check("sqlite_db", True,
                               f"Database exists — {size_mb:.2f} MB")
        else:
            self._update_check("sqlite_db", True,
                               "No database yet — will be created on first project")

    def _check_rag(self):
        doc_count = 0
        if os.path.isdir(str(config.DOCS_DIR)):
            for root, dirs, files in os.walk(str(config.DOCS_DIR)):
                for f in files:
                    if f.endswith((".md", ".txt", ".rst")):
                        doc_count += 1

        if doc_count > 0:
            self._update_check("rag_index", True,
                               f"{doc_count} documentation files found in .forge/docs/")
        else:
            self._update_check("rag_index", True,
                               "No docs yet — add .md/.txt files to ~/.forge/docs/")

    def _check_git(self):
        import subprocess
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                self._update_check("git_available", True, version)
            else:
                self._update_check("git_available", False, "Git not found")
        except FileNotFoundError:
            self._update_check("git_available", False,
                               "Git not installed — download from git-scm.com")
        except Exception as e:
            self._update_check("git_available", False, str(e))

    def _check_pytest(self):
        try:
            import pytest
            self._update_check("pytest_available", True,
                               f"pytest {pytest.__version__} available")
        except ImportError:
            self._update_check("pytest_available", False,
                               "pytest not installed — pip install pytest")

    def _check_ollama_network(self):
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{config.OLLAMA_HOST}/api/tags",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    self._update_check("ollama_network", True,
                                       f"Connected to {config.OLLAMA_HOST}")
                else:
                    self._update_check("ollama_network", False,
                                       f"HTTP {resp.status}")
        except Exception as e:
            self._update_check("ollama_network", False,
                               f"Cannot reach Ollama: {str(e)[:80]}")

    def _check_gemini_network(self):
        if not config.GEMINI_API_KEY:
            self._update_check("gemini_network", False,
                               "No API key — set GEMINI_API_KEY")
            return
        try:
            import urllib.request
            req = urllib.request.Request(
                "https://generativelanguage.googleapis.com/v1beta/models",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self._update_check("gemini_network", True,
                                   "Google AI API reachable")
        except Exception as e:
            self._update_check("gemini_network", False,
                               f"Cannot reach Google AI: {str(e)[:80]}")
