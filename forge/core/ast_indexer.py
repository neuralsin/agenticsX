"""
FORGE AST Indexer — AST-aware context retrieval for codebase slicing.
Replaces TF-IDF keyword matching with structural code understanding.
Uses Python's ast module for .py files, regex fallback for others.
"""

import ast
import os
import re
from typing import Optional

import config


class SymbolInfo:
    """Represents a code symbol extracted from AST."""

    __slots__ = ("kind", "name", "filepath", "line", "end_line",
                 "signature", "docstring", "parent", "imports")

    def __init__(self, kind: str, name: str, filepath: str, line: int,
                 end_line: int = 0, signature: str = "",
                 docstring: str = "", parent: str = "",
                 imports: list = None):
        self.kind = kind            # "function" | "class" | "method" | "import" | "variable"
        self.name = name
        self.filepath = filepath
        self.line = line
        self.end_line = end_line or line
        self.signature = signature
        self.docstring = docstring
        self.parent = parent        # Parent class name for methods
        self.imports = imports or []

    def to_dict(self) -> dict:
        return {
            "kind": self.kind, "name": self.name, "filepath": self.filepath,
            "line": self.line, "end_line": self.end_line,
            "signature": self.signature, "docstring": self.docstring,
            "parent": self.parent,
        }

    def __repr__(self):
        return f"<{self.kind} {self.name} @ {self.filepath}:{self.line}>"


class ASTIndexer:
    """
    Indexes a codebase using AST parsing for structural understanding.
    Provides symbol-level context retrieval instead of raw file dumps.
    """

    def __init__(self, project_path: str):
        self.project_path = project_path
        self._symbols: list[SymbolInfo] = []
        self._file_symbols: dict[str, list[SymbolInfo]] = {}
        self._indexed = False

    def index(self):
        """Index the entire project directory."""
        self._symbols.clear()
        self._file_symbols.clear()

        for root, dirs, files in os.walk(self.project_path):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in {
                ".forge", "__pycache__", ".git", ".venv", "venv",
                "node_modules", ".pytest_cache", ".mypy_cache",
                "dist", "build", ".tox",
            }]

            for filename in files:
                filepath = os.path.join(root, filename)
                ext = os.path.splitext(filename)[1].lower()

                if ext not in config.AST_SUPPORTED_EXTENSIONS:
                    continue

                rel_path = os.path.relpath(filepath, self.project_path)

                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except (IOError, OSError):
                    continue

                if ext == ".py":
                    symbols = self._parse_python(content, rel_path)
                else:
                    symbols = self._parse_generic(content, rel_path, ext)

                self._symbols.extend(symbols)
                self._file_symbols[rel_path] = symbols

        self._indexed = True

    def _parse_python(self, source: str, filepath: str) -> list[SymbolInfo]:
        """Parse a Python file using the ast module."""
        symbols = []
        try:
            tree = ast.parse(source, filename=filepath)
        except SyntaxError:
            return self._parse_generic(source, filepath, ".py")

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                # Check if it's a method (inside a class)
                parent = ""
                for potential_parent in ast.walk(tree):
                    if isinstance(potential_parent, ast.ClassDef):
                        for child in ast.iter_child_nodes(potential_parent):
                            if child is node:
                                parent = potential_parent.name
                                break

                sig = self._build_function_signature(node)
                doc = ast.get_docstring(node) or ""
                kind = "method" if parent else "function"

                symbols.append(SymbolInfo(
                    kind=kind, name=node.name, filepath=filepath,
                    line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    signature=sig,
                    docstring=doc[:200] if doc else "",
                    parent=parent,
                ))

            elif isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node) or ""
                bases = [self._get_name(b) for b in node.bases]
                sig = f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}"

                symbols.append(SymbolInfo(
                    kind="class", name=node.name, filepath=filepath,
                    line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    signature=sig,
                    docstring=doc[:200] if doc else "",
                ))

            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        symbols.append(SymbolInfo(
                            kind="import", name=alias.name,
                            filepath=filepath, line=node.lineno,
                            signature=f"import {alias.name}",
                        ))
                else:
                    module = node.module or ""
                    for alias in node.names:
                        symbols.append(SymbolInfo(
                            kind="import",
                            name=f"{module}.{alias.name}",
                            filepath=filepath, line=node.lineno,
                            signature=f"from {module} import {alias.name}",
                        ))

        return symbols

    def _build_function_signature(self, node) -> str:
        """Build a function signature string from an AST FunctionDef node."""
        args = []
        all_args = node.args

        # positional args
        defaults_offset = len(all_args.args) - len(all_args.defaults)
        for i, arg in enumerate(all_args.args):
            name = arg.arg
            annotation = ""
            if arg.annotation:
                annotation = f": {self._get_name(arg.annotation)}"

            default = ""
            default_idx = i - defaults_offset
            if default_idx >= 0 and default_idx < len(all_args.defaults):
                default = f"={self._get_literal(all_args.defaults[default_idx])}"

            args.append(f"{name}{annotation}{default}")

        # *args
        if all_args.vararg:
            args.append(f"*{all_args.vararg.arg}")

        # **kwargs
        if all_args.kwarg:
            args.append(f"**{all_args.kwarg.arg}")

        ret = ""
        if node.returns:
            ret = f" -> {self._get_name(node.returns)}"

        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        return f"{prefix} {node.name}({', '.join(args)}){ret}"

    def _get_name(self, node) -> str:
        """Extract a name from an AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Constant):
            return repr(node.value)
        elif isinstance(node, ast.Subscript):
            return f"{self._get_name(node.value)}[{self._get_name(node.slice)}]"
        elif isinstance(node, ast.Tuple):
            return f"({', '.join(self._get_name(e) for e in node.elts)})"
        elif isinstance(node, ast.List):
            return f"[{', '.join(self._get_name(e) for e in node.elts)}]"
        return "..."

    def _get_literal(self, node) -> str:
        """Get a literal value from an AST constant node."""
        if isinstance(node, ast.Constant):
            return repr(node.value)
        elif isinstance(node, ast.Name):
            return node.id
        return "..."

    def _parse_generic(self, source: str, filepath: str,
                       ext: str) -> list[SymbolInfo]:
        """
        Regex-based fallback for non-Python files.
        Extracts function/class definitions from JS/TS/Java/Go/Rust/C++.
        """
        symbols = []
        lines = source.split("\n")

        patterns = {
            ".js": [
                (r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)',
                 "function"),
                (r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?',
                 "class"),
                (r'const\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>',
                 "function"),
            ],
            ".ts": [
                (r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*[<(]',
                 "function"),
                (r'(?:export\s+)?class\s+(\w+)',
                 "class"),
                (r'(?:export\s+)?interface\s+(\w+)',
                 "class"),
            ],
            ".java": [
                (r'(?:public|private|protected)?\s*(?:static\s+)?(?:\w+\s+)?(\w+)\s*\(',
                 "function"),
                (r'(?:public|private)?\s*class\s+(\w+)',
                 "class"),
            ],
            ".go": [
                (r'func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(',
                 "function"),
                (r'type\s+(\w+)\s+struct',
                 "class"),
            ],
            ".rs": [
                (r'(?:pub\s+)?fn\s+(\w+)\s*[<(]',
                 "function"),
                (r'(?:pub\s+)?struct\s+(\w+)',
                 "class"),
                (r'(?:pub\s+)?enum\s+(\w+)',
                 "class"),
                (r'(?:pub\s+)?trait\s+(\w+)',
                 "class"),
                (r'impl(?:<[^>]+>)?\s+(\w+)',
                 "class"),
            ],
        }

        # Also cover .jsx/.tsx with JS/TS patterns
        ext_key = ext
        if ext in (".jsx", ".tsx"):
            ext_key = ".js" if ext == ".jsx" else ".ts"

        file_patterns = patterns.get(ext_key, [])
        if not file_patterns and ext == ".py":
            file_patterns = [
                (r'def\s+(\w+)\s*\(', "function"),
                (r'class\s+(\w+)', "class"),
            ]

        for line_num, line in enumerate(lines, 1):
            for pattern, kind in file_patterns:
                match = re.search(pattern, line)
                if match:
                    name = match.group(1)
                    symbols.append(SymbolInfo(
                        kind=kind, name=name, filepath=filepath,
                        line=line_num, signature=line.strip()[:120],
                    ))

        return symbols

    def get_all_symbols(self) -> list[SymbolInfo]:
        """Get all indexed symbols."""
        if not self._indexed:
            self.index()
        return self._symbols

    def get_file_symbols(self, filepath: str) -> list[SymbolInfo]:
        """Get symbols for a specific file."""
        if not self._indexed:
            self.index()
        return self._file_symbols.get(filepath, [])

    def get_symbol_map(self) -> str:
        """
        Get a compact symbol map of the entire project.
        Suitable for injection into agent context.
        """
        if not self._indexed:
            self.index()

        lines = ["[PROJECT SYMBOL MAP]"]
        current_file = ""

        for sym in sorted(self._symbols,
                          key=lambda s: (s.filepath, s.line)):
            if sym.kind == "import":
                continue  # Skip imports in map

            if sym.filepath != current_file:
                current_file = sym.filepath
                lines.append(f"\n--- {current_file} ---")

            indent = "  " if sym.parent else ""
            doc_suffix = f'  # {sym.docstring[:60]}' if sym.docstring else ""
            lines.append(
                f"{indent}L{sym.line}: {sym.signature}{doc_suffix}"
            )

        return "\n".join(lines)

    def get_relevant_symbols(self, task: str,
                             max_tokens: int = 3000) -> str:
        """
        Get symbols most relevant to a task description.
        Uses name/signature/docstring matching instead of TF-IDF.
        """
        if not self._indexed:
            self.index()

        task_words = set(re.findall(r'\w+', task.lower()))

        scored = []
        for sym in self._symbols:
            if sym.kind == "import":
                continue

            score = 0
            sym_words = set(re.findall(
                r'\w+',
                f"{sym.name} {sym.signature} {sym.docstring} "
                f"{sym.filepath} {sym.parent}".lower()
            ))

            # Name match is highest priority
            name_words = set(re.findall(r'[a-z]+', sym.name.lower()))
            score += len(task_words & name_words) * 5

            # Filepath match
            path_words = set(re.findall(r'\w+', sym.filepath.lower()))
            score += len(task_words & path_words) * 3

            # Signature/docstring match
            score += len(task_words & sym_words)

            if score > 0:
                scored.append((score, sym))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Build context within token limit
        from core.token_counter import count_tokens

        parts = ["[RELEVANT CODE SYMBOLS]"]
        tokens_used = count_tokens(parts[0])
        current_file = ""

        for score, sym in scored:
            entry = ""
            if sym.filepath != current_file:
                current_file = sym.filepath
                entry = f"\n--- {current_file} ---\n"

            indent = "  " if sym.parent else ""
            doc = f'\n{indent}  """{sym.docstring}"""' if sym.docstring else ""
            entry += f"{indent}L{sym.line}-{sym.end_line}: {sym.signature}{doc}\n"

            entry_tokens = count_tokens(entry)
            if tokens_used + entry_tokens > max_tokens:
                break

            parts.append(entry)
            tokens_used += entry_tokens

        return "".join(parts)

    def get_function_source(self, filepath: str, function_name: str,
                            project_path: str = None) -> Optional[str]:
        """Get the full source code of a specific function."""
        proj = project_path or self.project_path
        abs_path = os.path.join(proj, filepath)

        for sym in self.get_file_symbols(filepath):
            if sym.name == function_name and sym.kind in ("function", "method"):
                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    return "".join(
                        lines[sym.line - 1:sym.end_line]
                    )
                except (IOError, IndexError):
                    return None
        return None
