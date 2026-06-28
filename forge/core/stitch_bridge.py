"""
FORGE Stitch Bridge — Integrates with Stitch MCP for design system import.
Accepts a Stitch project ID, fetches design tokens and screen HTML,
converts to structured context for the CODER agent.
"""

import json
import re
import os
from typing import Optional

import config


class StitchBridge:
    """
    Imports design systems and screen designs from Stitch MCP projects.
    Converts to a structured format that agents can use as context.
    """

    def __init__(self):
        self._project_cache = {}
        self._screens_cache = {}

    def fetch_project(self, project_id: str) -> Optional[dict]:
        """
        Fetch project data from Stitch MCP.
        Since MCP is accessed via the IDE, this method parses
        cached/local data or provides a structured interface.
        """
        if project_id in self._project_cache:
            return self._project_cache[project_id]
        return None

    def set_project_data(self, project_id: str, data: dict):
        """Set project data (called by GUI after MCP fetch)."""
        self._project_cache[project_id] = data

    def set_screens_data(self, project_id: str, screens: list[dict]):
        """Set screens data (called by GUI after MCP fetch)."""
        self._screens_cache[project_id] = screens

    def extract_design_system(self, project_data: dict) -> dict:
        """
        Extract design tokens from a Stitch project.
        Returns structured design system with colors, typography, spacing.
        """
        theme = project_data.get("designTheme", {})

        design_system = {
            "name": project_data.get("title", "Untitled"),
            "color_mode": theme.get("colorMode", "DARK"),
            "colors": {},
            "typography": {},
            "spacing": {},
            "roundness": theme.get("roundness", "ROUND_FOUR"),
        }

        # Extract named colors
        named_colors = theme.get("namedColors", {})
        for name, value in named_colors.items():
            design_system["colors"][name] = value

        # Extract typography
        typo = theme.get("typography", {})
        for name, spec in typo.items():
            design_system["typography"][name] = {
                "family": spec.get("fontFamily", "Inter"),
                "size": spec.get("fontSize", "14px"),
                "weight": spec.get("fontWeight", "400"),
                "line_height": spec.get("lineHeight", "1.6"),
            }

        # Extract spacing
        spacing = theme.get("spacing", {})
        for name, value in spacing.items():
            design_system["spacing"][name] = value

        # Extract design.md if available
        design_md = theme.get("designMd", "")
        if design_md:
            design_system["design_md"] = design_md

        return design_system

    def design_system_to_context(self, design_system: dict) -> str:
        """
        Convert a design system to a context injection string
        suitable for the CODER agent's prompt.
        """
        parts = ["[DESIGN SYSTEM — from Stitch]"]
        parts.append(f"Project: {design_system.get('name', 'Unknown')}")
        parts.append(f"Mode: {design_system.get('color_mode', 'DARK')}")
        parts.append("")

        # Colors
        colors = design_system.get("colors", {})
        if colors:
            parts.append("### Colors")
            # Group by semantic purpose
            primary_colors = {}
            surface_colors = {}
            semantic_colors = {}

            for name, value in sorted(colors.items()):
                if "surface" in name or "background" in name:
                    surface_colors[name] = value
                elif any(k in name for k in ["primary", "secondary", "tertiary"]):
                    primary_colors[name] = value
                else:
                    semantic_colors[name] = value

            if primary_colors:
                parts.append("Brand:")
                for n, v in list(primary_colors.items())[:10]:
                    parts.append(f"  {n}: {v}")

            if surface_colors:
                parts.append("Surfaces:")
                for n, v in list(surface_colors.items())[:8]:
                    parts.append(f"  {n}: {v}")

            if semantic_colors:
                parts.append("Semantic:")
                for n, v in list(semantic_colors.items())[:10]:
                    parts.append(f"  {n}: {v}")

            parts.append("")

        # Typography
        typo = design_system.get("typography", {})
        if typo:
            parts.append("### Typography")
            for name, spec in typo.items():
                parts.append(
                    f"  {name}: {spec['family']} "
                    f"{spec['size']}/{spec['weight']}"
                )
            parts.append("")

        # Spacing
        spacing = design_system.get("spacing", {})
        if spacing:
            parts.append("### Spacing")
            for name, value in spacing.items():
                parts.append(f"  {name}: {value}")
            parts.append("")

        return "\n".join(parts)

    def extract_screen_html(self, screen_data: dict) -> str:
        """Extract HTML code from a Stitch screen."""
        html_code = screen_data.get("htmlCode", {})
        # The actual HTML content would be fetched via the download URL
        # For local use, return the reference
        download_url = html_code.get("downloadUrl", "")
        return download_url

    def screens_to_context(self, screens: list[dict]) -> str:
        """Convert screen list to a context summary."""
        if not screens:
            return ""

        parts = ["[STITCH SCREENS]"]
        for screen in screens:
            title = screen.get("title", "Untitled")
            width = screen.get("width", "?")
            height = screen.get("height", "?")
            parts.append(f"  • {title} ({width}×{height})")

        return "\n".join(parts)

    def get_full_context(self, project_id: str) -> str:
        """
        Get the complete design context for a Stitch project.
        Combines design system + screens into one injection string.
        """
        project = self._project_cache.get(project_id)
        if not project:
            return ""

        ds = self.extract_design_system(project)
        context = self.design_system_to_context(ds)

        screens = self._screens_cache.get(project_id, [])
        if screens:
            context += "\n\n" + self.screens_to_context(screens)

        return context

    def save_design_spec(self, project_id: str,
                         output_path: str) -> bool:
        """Save the extracted design spec to a file in the project."""
        context = self.get_full_context(project_id)
        if not context:
            return False

        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(context)
            return True
        except IOError:
            return False

    @staticmethod
    def parse_design_md(design_md: str) -> dict:
        """
        Parse a Stitch design.md YAML frontmatter into structured data.
        Returns {colors: {}, typography: {}, spacing: {}, ...}
        """
        result = {"colors": {}, "typography": {}, "spacing": {},
                  "brand_description": ""}

        # Extract YAML frontmatter between ---
        frontmatter_match = re.search(
            r'^---\s*\n(.+?)\n---',
            design_md, re.DOTALL
        )

        if frontmatter_match:
            yaml_text = frontmatter_match.group(1)

            # Simple YAML-like parsing for colors
            current_section = ""
            for line in yaml_text.split("\n"):
                stripped = line.strip()
                if stripped.startswith("colors:"):
                    current_section = "colors"
                elif stripped.startswith("typography:"):
                    current_section = "typography"
                elif stripped.startswith("spacing:"):
                    current_section = "spacing"
                elif ":" in stripped and current_section:
                    key, value = stripped.split(":", 1)
                    key = key.strip().strip("'\"")
                    value = value.strip().strip("'\"")
                    if value:
                        result[current_section][key] = value

        # Extract brand description (text after frontmatter)
        if frontmatter_match:
            rest = design_md[frontmatter_match.end():]
            result["brand_description"] = rest.strip()[:1000]

        return result
