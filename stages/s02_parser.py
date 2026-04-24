"""
stages/s02_parser.py - Stage 02: Repository Parser.

Walks source files in the cloned repo and extracts lightweight structure:
function names, class names, imports, AST node count, and file stats.

Primary library : tree-sitter (py-tree-sitter + tree-sitter-language-pack)
Fallback        : tree-sitter-languages, then heuristic line parsing
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Callable, Generator

from core.config import PipelineConfig, RepoMeta, ParsedFile
from core.logger import get_logger

log = get_logger("s02_parser")

# ---------------------------------------------------------------------------
# Language -> tree-sitter grammar mapping
# ---------------------------------------------------------------------------
_TS_LANG_MAP: dict[str, str] = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "java": "java",
    "go": "go",
    "rust": "rust",
    "cpp": "cpp",
    "c": "c",
    "ruby": "ruby",
    "php": "php",
    "csharp": "c_sharp",
    "kotlin": "kotlin",
    "scala": "scala",
}

_EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".ipynb": "python",  # Jupyter notebooks (extract code cells as Python)
    ".js": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".kt": "kotlin",
    ".scala": "scala",
    ".swift": "swift",
    ".m": "objectivec",
    ".dart": "dart",
    ".r": "r",
    ".R": "r",
    ".groovy": "groovy",
    ".sql": "sql",
    ".sh": "sh",
    ".bash": "bash",
    ".lua": "lua",
    ".clj": "clojure",
    ".exs": "elixir",
    ".hs": "haskell",
    ".pl": "perl",
    ".jl": "julia",
    ".Dockerfile": "dockerfile",
    ".dockerfile": "dockerfile",
}

# tree-sitter node types per language that represent functions/methods
_FUNCTION_NODE_TYPES: dict[str, list[str]] = {
    "python": ["function_definition", "async_function_definition"],
    "javascript": ["function_declaration", "arrow_function", "method_definition"],
    "typescript": ["function_declaration", "arrow_function", "method_definition"],
    "java": ["method_declaration", "constructor_declaration"],
    "go": ["function_declaration", "method_declaration"],
    "rust": ["function_item"],
    "cpp": ["function_definition"],
    "c": ["function_definition"],
    "ruby": ["method", "singleton_method"],
    "php": ["function_definition", "method_declaration"],
}

_CLASS_NODE_TYPES: dict[str, list[str]] = {
    "python": ["class_definition"],
    "javascript": ["class_declaration"],
    "typescript": ["class_declaration"],
    "java": ["class_declaration", "interface_declaration"],
    "go": ["type_declaration"],
    "rust": ["struct_item", "impl_item", "trait_item"],
    "cpp": ["class_specifier", "struct_specifier"],
    "c": ["struct_specifier"],
    "ruby": ["class", "module"],
    "php": ["class_declaration", "interface_declaration"],
}

_IDENT = r"[A-Za-z_][A-Za-z0-9_]*"

_JS_FUNC_DECL_RE = re.compile(r"^\s*(?:export\s+)?function\s+(" + _IDENT + r")\s*\(")
_JS_ARROW_DECL_RE = re.compile(
    r"^\s*(?:export\s+)?(?:const|let|var)\s+(" + _IDENT + r")\s*=\s*"
    r"(?:async\s*)?(?:\([^)]*\)|" + _IDENT + r")\s*=>"
)
_JS_CLASS_DECL_RE = re.compile(r"^\s*(?:export\s+)?class\s+(" + _IDENT + r")\b")
_JS_METHOD_DECL_RE = re.compile(r"^\s*(?:async\s+)?(" + _IDENT + r")\s*\([^;]*\)\s*\{")
_JS_NON_METHOD_HEADS = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "function",
    "return",
    "class",
    "const",
    "let",
    "var",
    "else",
    "do",
    "try",
    "typeof",
    "new",
}

_JAVA_CLASS_DECL_RE = re.compile(
    r"^\s*(?:public\s+)?(?:class|interface|enum)\s+(" + _IDENT + r")\b"
)
_JAVA_METHOD_DECL_RE = re.compile(
    r"^\s*(?:public|protected|private|static|final|abstract|synchronized|native|"
    r"default|strictfp|\s)+[\w<>\[\], ?]+\s+(" + _IDENT + r")\s*\([^;{)]*\)\s*"
    r"(?:throws\b[^;{]*)?\{?\s*$"
)
_JAVA_CTOR_DECL_RE = re.compile(
    r"^\s*(?:public|protected|private)\s+(" + _IDENT + r")\s*\([^;{)]*\)\s*"
    r"(?:throws\b[^;{]*)?\{?\s*$"
)


def run(repo_meta: RepoMeta, cfg: PipelineConfig) -> list[ParsedFile]:
    """
    Parse every supported source file in the repo.

    Returns
    -------
    list[ParsedFile]
        One entry per source file (skips oversized files).
    """
    ts_parser_factory = _init_treesitter_factory()
    ts_parser_cache: dict[str, Any] = {}
    ts_disabled_langs: set[str] = set()

    base = Path(repo_meta.local_path)
    results: list[ParsedFile] = []

    for file_path in _iter_source_files(base, cfg):
        lang = _EXT_TO_LANG.get(file_path.suffix.lower())
        if not lang:
            continue

        rel_path = str(file_path.relative_to(base))
        size = file_path.stat().st_size

        if size > cfg.max_file_size_bytes:
            log.debug("Skipping %s - too large (%d bytes)", rel_path, size)
            continue

        try:
            # Special handling for Jupyter notebooks
            if file_path.suffix.lower() == ".ipynb":
                source = _extract_jupyter_code(file_path)
            else:
                source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            log.warning("Cannot read %s: %s", rel_path, exc)
            continue

        line_count = source.count("\n") + 1

        parser = None
        ts_lang_name = _TS_LANG_MAP.get(lang)
        if ts_parser_factory and ts_lang_name:
            parser = ts_parser_cache.get(ts_lang_name)
            if parser is None and ts_lang_name not in ts_disabled_langs:
                try:
                    parser = ts_parser_factory(ts_lang_name)
                    ts_parser_cache[ts_lang_name] = parser
                except Exception as exc:
                    ts_disabled_langs.add(ts_lang_name)
                    log.warning(
                        "tree-sitter unavailable for language '%s' (%s) - using heuristic parser",
                        ts_lang_name,
                        exc,
                    )

        if parser is not None:
            parsed = _parse_with_treesitter(
                rel_path,
                lang,
                source,
                size,
                line_count,
                parser,
            )
        else:
            parsed = _parse_basic(rel_path, lang, source, size, line_count)

        results.append(parsed)

    log.info("Parser done - %d files parsed", len(results))
    return results


# ---------------------------------------------------------------------------
# tree-sitter bootstrap and parsing
# ---------------------------------------------------------------------------

def _extract_jupyter_code(notebook_path: Path) -> str:
    """
    Extract Python code from a Jupyter notebook.
    Joins code cells with newlines.
    """
    try:
        import json
        notebook_content = json.loads(notebook_path.read_text(encoding="utf-8", errors="replace"))
        code_cells = []
        for cell in notebook_content.get("cells", []):
            if cell.get("cell_type") == "code":
                source = cell.get("source", [])
                if isinstance(source, list):
                    code_cells.append("".join(source))
                else:
                    code_cells.append(source)
        return "\n\n".join(code_cells)
    except Exception as exc:
        log.warning("Failed to extract code from Jupyter notebook %s: %s", notebook_path, exc)
        return ""


def _init_treesitter_factory() -> Callable[[str], Any] | None:
    """
    Build a parser factory compatible with multiple tree-sitter API versions.

    Returns None when tree-sitter cannot be used in this environment.
    """
    candidates: list[tuple[str, Callable[[], Callable[[str], Any] | None]]] = [
        ("tree-sitter-language-pack", _init_language_pack_factory),
        ("tree-sitter-languages", _init_legacy_languages_factory),
    ]

    for backend_name, init_backend in candidates:
        factory = init_backend()
        if factory is None:
            continue
        if _probe_treesitter_factory(factory, backend_name):
            return factory

    log.warning(
        "No compatible tree-sitter backend found. tree-sitter=%s, tree-sitter-language-pack=%s, tree-sitter-languages=%s - using heuristic parser",
        _package_version("tree-sitter"),
        _package_version("tree-sitter-language-pack"),
        _package_version("tree-sitter-languages"),
    )
    return None


def _init_language_pack_factory() -> Callable[[str], Any] | None:
    try:
        from tree_sitter_language_pack import get_parser as tslp_get_parser
    except ImportError:
        return None

    def _factory(ts_lang_name: str) -> Any:
        return tslp_get_parser(ts_lang_name)

    return _factory


def _init_legacy_languages_factory() -> Callable[[str], Any] | None:
    try:
        from tree_sitter_languages import get_language as ts_get_language
        from tree_sitter_languages import get_parser as ts_get_parser
    except ImportError:
        return None

    def _factory(ts_lang_name: str) -> Any:
        try:
            parser = ts_get_parser(ts_lang_name)
            if hasattr(parser, "parse"):
                return parser
        except Exception:
            pass

        language_obj = ts_get_language(ts_lang_name)
        return _build_ts_parser(language_obj)

    return _factory


def _probe_treesitter_factory(
    factory: Callable[[str], Any],
    backend_name: str,
) -> bool:
    try:
        probe = factory("python")
        probe.parse(b"def _probe():\n    pass\n")
        log.info("Using tree-sitter backend: %s", backend_name)
        return True
    except Exception as exc:
        log.warning(
            "tree-sitter backend '%s' unavailable (%s)",
            backend_name,
            exc,
        )
        return False


def _package_version(package: str) -> str:
    try:
        import importlib.metadata as metadata

        return metadata.version(package)
    except Exception:
        return "unknown"


def _build_ts_parser(language_obj: Any) -> Any:
    """Create a parser from a language object across old/new tree-sitter APIs."""
    from tree_sitter import Parser as TSParser

    try:
        parser = TSParser(language_obj)
        if hasattr(parser, "parse"):
            return parser
    except Exception:
        parser = TSParser()

    if hasattr(parser, "set_language"):
        parser.set_language(language_obj)
    else:
        parser.language = language_obj

    return parser


def _parse_with_treesitter(
    rel_path: str,
    lang: str,
    source: str,
    size: int,
    line_count: int,
    parser,
) -> ParsedFile:
    try:
        tree = parser.parse(bytes(source, "utf-8"))
        root = tree.root_node

        function_names = _extract_names(root, _FUNCTION_NODE_TYPES.get(lang, []), source)
        class_names = _extract_names(root, _CLASS_NODE_TYPES.get(lang, []), source)
        imports = _extract_imports(root, lang, source)
        node_count = _count_nodes(root)
        parse_error = root.has_error

        return ParsedFile(
            path=rel_path,
            language=lang,
            size_bytes=size,
            line_count=line_count,
            function_names=function_names,
            class_names=class_names,
            imports=imports,
            ast_node_count=node_count,
            parse_error=parse_error,
        )
    except Exception as exc:
        log.warning("tree-sitter failed on %s: %s", rel_path, exc)
        return _parse_basic(rel_path, lang, source, size, line_count)


def _extract_names(node, node_types: list[str], source: str) -> list[str]:
    """Walk the AST and collect identifier names for matching node types."""
    names: list[str] = []
    _walk(node, node_types, source, names)
    return names[:100]


def _walk(node, target_types: list[str], source: str, acc: list[str]) -> None:
    if node.type in target_types:
        name = _extract_node_name(node, source)
        if name:
            acc.append(name)
    for child in node.children:
        _walk(child, target_types, source, acc)


def _extract_node_name(node, source: str) -> str | None:
    candidate_types = {
        "identifier",
        "name",
        "property_identifier",
        "type_identifier",
    }

    name_node = None

    # Most grammars expose a "name" field for declarations.
    if hasattr(node, "child_by_field_name"):
        try:
            name_node = node.child_by_field_name("name")
        except Exception:
            name_node = None

    # JavaScript arrow functions are often anonymous nodes assigned via const X = () => {}
    if name_node is None and node.type in {"arrow_function", "function"}:
        parent = getattr(node, "parent", None)
        if parent is not None and parent.type == "variable_declarator":
            try:
                name_node = parent.child_by_field_name("name")
            except Exception:
                name_node = None

    if name_node is None:
        for child in node.children:
            if child.type in candidate_types:
                name_node = child
                break

    if name_node is None:
        return None

    return source[name_node.start_byte : name_node.end_byte]


def _extract_imports(node, lang: str, source: str) -> list[str]:
    """Extract import statements (first 50)."""
    import_types = {
        "python": ["import_statement", "import_from_statement"],
        "javascript": ["import_declaration"],
        "typescript": ["import_declaration"],
        "java": ["import_declaration"],
        "go": ["import_declaration"],
        "rust": ["use_declaration"],
    }
    target = import_types.get(lang, [])
    imports: list[str] = []
    _collect_text(node, target, source, imports)
    return imports[:50]


def _collect_text(node, target_types: list[str], source: str, acc: list[str]) -> None:
    if node.type in target_types:
        acc.append(source[node.start_byte : node.end_byte].split("\n", 1)[0].strip())
    for child in node.children:
        _collect_text(child, target_types, source, acc)


def _count_nodes(node) -> int:
    return 1 + sum(_count_nodes(c) for c in node.children)


# ---------------------------------------------------------------------------
# Fallback: heuristic parser (no tree-sitter)
# ---------------------------------------------------------------------------

def _parse_basic(
    rel_path: str,
    lang: str,
    source: str,
    size: int,
    line_count: int,
) -> ParsedFile:
    """Language-aware heuristic parsing when tree-sitter is unavailable."""
    functions: list[str] = []
    classes: list[str] = []
    imports: list[str] = []

    if lang == "python":
        functions, classes, imports = _parse_python_basic(source)
    elif lang in {"javascript", "typescript"}:
        functions, classes, imports = _parse_js_ts_basic(source)
    elif lang == "java":
        functions, classes, imports = _parse_java_basic(source)
    else:
        imports = _parse_generic_imports(lang, source)

    return ParsedFile(
        path=rel_path,
        language=lang,
        size_bytes=size,
        line_count=line_count,
        function_names=_unique_limited(functions, 100),
        class_names=_unique_limited(classes, 50),
        imports=_unique_limited(imports, 50),
        ast_node_count=0,
        parse_error=False,
    )


def _parse_python_basic(source: str) -> tuple[list[str], list[str], list[str]]:
    functions: list[str] = []
    classes: list[str] = []
    imports: list[str] = []

    fn_re = re.compile(r"^\s*(?:async\s+def|def)\s+(" + _IDENT + r")\s*\(")
    cls_re = re.compile(r"^\s*class\s+(" + _IDENT + r")\b")

    for raw_line in source.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        if stripped.startswith(("import ", "from ")):
            imports.append(stripped)

        m = fn_re.match(raw_line)
        if m:
            functions.append(m.group(1))
            continue

        m = cls_re.match(raw_line)
        if m:
            classes.append(m.group(1))

    return functions, classes, imports


def _parse_js_ts_basic(source: str) -> tuple[list[str], list[str], list[str]]:
    functions: list[str] = []
    classes: list[str] = []
    imports: list[str] = []

    for raw_line in source.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("//"):
            continue

        if stripped.startswith("import "):
            imports.append(stripped.rstrip(";"))
        elif "require(" in stripped and stripped.startswith(("const ", "let ", "var ")):
            imports.append(stripped.rstrip(";"))

        m = _JS_FUNC_DECL_RE.match(raw_line)
        if m:
            functions.append(m.group(1))
            continue

        m = _JS_ARROW_DECL_RE.match(raw_line)
        if m:
            functions.append(m.group(1))
            continue

        m = _JS_CLASS_DECL_RE.match(raw_line)
        if m:
            classes.append(m.group(1))
            continue

        m = _JS_METHOD_DECL_RE.match(raw_line)
        if m:
            name = m.group(1)
            if name not in _JS_NON_METHOD_HEADS:
                functions.append(name)

    return functions, classes, imports


def _parse_java_basic(source: str) -> tuple[list[str], list[str], list[str]]:
    functions: list[str] = []
    classes: list[str] = []
    imports: list[str] = []

    for raw_line in source.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        if stripped.startswith("import "):
            imports.append(stripped.rstrip(";"))

        m = _JAVA_CLASS_DECL_RE.match(raw_line)
        if m:
            classes.append(m.group(1))
            continue

        m = _JAVA_METHOD_DECL_RE.match(raw_line)
        if m:
            functions.append(m.group(1))
            continue

        m = _JAVA_CTOR_DECL_RE.match(raw_line)
        if m:
            functions.append(m.group(1))

    return functions, classes, imports


def _parse_generic_imports(lang: str, source: str) -> list[str]:
    imports: list[str] = []
    for raw_line in source.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        if lang in {"cpp", "c"} and stripped.startswith("#include"):
            imports.append(stripped)
        elif lang == "go" and stripped.startswith("import "):
            imports.append(stripped)
        elif lang == "rust" and stripped.startswith("use "):
            imports.append(stripped)
        elif lang == "ruby" and stripped.startswith("require "):
            imports.append(stripped)
        elif lang == "php" and stripped.startswith("use "):
            imports.append(stripped)

    return imports


def _unique_limited(items: list[str], limit: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
        if len(out) >= limit:
            break

    return out


# ---------------------------------------------------------------------------
# File iteration
# ---------------------------------------------------------------------------

def _iter_source_files(base: Path, cfg: PipelineConfig) -> Generator[Path, None, None]:
    skip_dirs = {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "dist",
        "build",
        ".tox",
        ".mypy_cache",
    }
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fname in files:
            fp = Path(root) / fname
            if fp.suffix.lower() in _EXT_TO_LANG:
                yield fp
