#!/usr/bin/env python3
import argparse
import json
import math
import os
import random
import re
import sys
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent


# Load overrides from paths.env (optional)
def load_paths_env(path: Path) -> dict[str, str]:
    """Loads environment variables from a file.

    Args:
        path: Path to the environment file.

    Returns:
        Dictionary of environment variables.
    """
    if not path.exists():
        return {}
    variables = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("#"):
            continue
        if "=" not in stripped_line:
            continue
        k, v = stripped_line.split("=", 1)
        k = k.strip().lstrip("$")
        v = v.strip()
        # Support windows path escaping and env expansion
        v = v.replace("\\", os.sep)
        variables[k] = v

    # Expand references to variables defined in the same file.
    def expand_value(value: str) -> str:
        pattern = re.compile(r"\$(\w+)|\$\{(\w+)\}")
        previous = None
        while previous != value:
            previous = value
            value = pattern.sub(
                lambda match: variables.get(
                    match.group(1) or match.group(2),
                    os.environ.get(match.group(1) or match.group(2), match.group(0)),
                ),
                value,
            )
        return value

    for key, raw_value in list(variables.items()):
        variables[key] = expand_value(raw_value)

    return variables


_path_vars = load_paths_env(DATA_DIR / "paths.env")
PROFILE_DIR = Path(_path_vars.get("PROFILES", DATA_DIR / "profiles"))
PROFILE_FILE = PROFILE_DIR / "profiles.json"
CATALOG_DIR = Path(_path_vars.get("CATALOG", DATA_DIR / "catalog"))

random_generator = random.SystemRandom()

VERY_LOW_ENTROPY = 28
LOW_ENTROPY = 40
MEDIUM_ENTROPY = 60
HIGH_ENTROPY = 80
MIN_ORDER_ENTRIES = 2


def load_profiles(path: Path) -> dict[str, Any]:
    """Loads profiles from a JSON file.

    Args:
        path: Path to the profiles JSON file.

    Returns:
        Dictionary of profiles.

    Raises:
        JSONDecodeError: If the file is not valid JSON.
    """
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    try:
        profiles = json.loads(text)
    except json.JSONDecodeError:
        profiles = {}
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            profiles[key.strip()] = value.strip()
        return profiles

    if not isinstance(profiles, dict):
        message = f"Profiles file {path} did not contain a JSON object"
        raise TypeError(message)
    return profiles


def normalize_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("/"):
        normalized = normalized[1:]
    return normalized


def load_json_file(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def load_list_file(path: Path) -> list[str]:
    values = load_json_file(path)
    if isinstance(values, list):
        return values
    return []


def resolve_profile_source_files(source_reference: str) -> dict[str, Any]:
    if "#" not in source_reference:
        message = f"Invalid profile source reference: '{source_reference}'"
        raise ValueError(message)

    ref_path, key = source_reference.split("#", 1)
    ref_path = normalize_path(ref_path)
    source_file = PROFILE_DIR / ref_path
    if not source_file.exists():
        source_file = DATA_DIR / ref_path

    data = load_json_file(source_file)
    if data is None or not isinstance(data, dict):
        message = f"Unable to load profile source '{ref_path}' from {source_file}"
        raise FileNotFoundError(message)

    if key not in data:
        message = f"Source key '{key}' not found in {source_file}"
        raise ValueError(message)

    profile_data = data[key]
    if not isinstance(profile_data, dict) or "files" not in profile_data:
        message = f"Source '{source_reference}' must contain a 'files' object"
        raise ValueError(message)

    if not isinstance(profile_data["files"], dict):
        message = f"'files' in source '{source_reference}' must be an object"
        raise TypeError(message)

    return profile_data["files"]


def resolve_profile_files(files_spec: Any) -> dict[str, Any]:
    if isinstance(files_spec, dict):
        return files_spec
    if isinstance(files_spec, str):
        return resolve_profile_source_files(files_spec)
    message = "files must be either an object or a source reference string"
    raise ValueError(message)


def load_all_separators() -> list[str]:
    candidate_path = CATALOG_DIR / "common" / "separators.json"
    if candidate_path.exists():
        separators = load_json_file(candidate_path)
        if isinstance(separators, list):
            return separators

    message = "Could not load separators from catalog/common/separators.json"
    raise FileNotFoundError(message)


def load_delimiter_values(file_name: str) -> list[str]:
    candidate_path = CATALOG_DIR / "common" / "delimiters" / file_name
    if candidate_path.exists():
        values = load_json_file(candidate_path)
        if isinstance(values, list):
            return values
    message = f"Could not load delimiters from catalog/common/delimiters/{file_name}"
    raise FileNotFoundError(message)


def resolve_delimiter_type(key: str) -> str:
    if ":" not in key:
        return key
    prefix, suffix = key.split(":", 1)
    if prefix == "subject":
        return "subject"
    return suffix


def delimiter_file_name(left_key: str, right_key: str) -> str:
    left_type = resolve_delimiter_type(left_key)
    right_type = resolve_delimiter_type(right_key)
    return f"{left_type}-{right_type}.json"


def select_supplemental_value(
    values: list[str], odds: dict[str, Any] | None = None,
) -> str:
    if not values:
        raise ValueError("Supplemental values list must not be empty")

    odds = odds or {}
    odds_space = odds.get("space")
    if isinstance(odds_space, (int, float)) and 0 < odds_space <= 100:
        space_values = [value for value in values if value == " "]
        if space_values:
            if random_generator.randrange(100) < int(odds_space):
                return random_generator.choice(space_values)
            non_space_values = [value for value in values if value != " "]
            if non_space_values:
                return random_generator.choice(non_space_values)
    return random_generator.choice(values)


def feature_triggers(feature_def: dict[str, Any]) -> bool:
    if not isinstance(feature_def, dict):
        return False
    if not feature_def.get("enabled", False):
        return False
    odds = feature_def.get("odds", 0)
    if not isinstance(odds, (int, float)) or odds <= 0:
        return False
    return random_generator.randrange(100) < int(odds)


def build_feature_candidates(feature_def: dict[str, Any]) -> list[str]:
    if not isinstance(feature_def, dict):
        raise TypeError("Feature definition must be an object")

    candidates: list[str] = []
    file_sources = feature_def.get("files", {})
    if not isinstance(file_sources, dict):
        raise TypeError("Feature files must be an object")

    for source in file_sources.values():
        if not isinstance(source, str):
            raise TypeError("Feature file references must be strings")
        values = list_from_name(source)
        if values is None:
            raise ValueError(f"Unknown list token/path: '{source}'")
        candidates.extend(str(value) for value in values)

    explicit_values = feature_def.get("values", [])
    if not isinstance(explicit_values, list):
        raise TypeError("Feature values must be a list")
    for value in explicit_values:
        if not isinstance(value, str):
            raise TypeError("Feature values must be strings")
        candidates.append(value)

    return candidates


def build_feature_value(feature_def: dict[str, Any]) -> str:
    if not feature_triggers(feature_def):
        return ""
    values = build_feature_candidates(feature_def)
    if not values:
        return ""
    return str(random_generator.choice(values))


def build_separator_candidates(profile_def: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    for feature_name in ("separators", "space"):
        feature_def = profile_def.get(feature_name)
        if isinstance(feature_def, dict) and feature_triggers(feature_def):
            candidates.extend(build_feature_candidates(feature_def))
    return candidates


def format_delimiter_value(separator: str) -> str:
    token = separator.strip()
    if token == "":
        return separator
    if token.isspace():
        return " "
    if re.fullmatch(r"[^\w\s]+", token):
        if token in {
            ",",
            ";",
            ":",
            ".",
            "!",
            "?",
            "...",
            "!!",
            "!!!",
            "?!",
            "!?",
            "??",
            "???",
        }:
            return token + " "
        return f" {token} "
    return f" {token} "


def build_delimiter_values(
    keys: list[str],
    odds: dict[str, Any] | None = None,
    delimiter_feature: dict[str, Any] | None = None,
) -> list[str]:
    if len(keys) < 2:
        return []

    odds = odds or {}

    explicit_values: list[str] = []
    if isinstance(delimiter_feature, dict):
        explicit_values = delimiter_feature.get("values", [])
        if not isinstance(explicit_values, list):
            raise TypeError("delimiters.values must be a list")
        for value in explicit_values:
            if not isinstance(value, str):
                raise TypeError("delimiters.values must be strings")

    separators: list[str] = []
    for left, right in zip(keys, keys[1:]):
        file_name = delimiter_file_name(left, right)
        try:
            typed_values = load_delimiter_values(file_name) or []
        except FileNotFoundError:
            typed_values = []

        pair_candidates = [str(value) for value in explicit_values] + [
            str(value) for value in typed_values
        ]
        if not pair_candidates:
            return []
        separators.append(
            format_delimiter_value(select_supplemental_value(pair_candidates, odds)),
        )
    return separators


def build_separator_values_for_profile(
    profile_def: dict[str, Any],
    keys: list[str],
    order: str,
    randomize: bool = False,
) -> tuple[list[str], list[str], bool]:
    delimiter_feature = profile_def.get("delimiters")
    if isinstance(delimiter_feature, dict):
        if feature_triggers(delimiter_feature):
            delimiter_values = build_delimiter_values(
                keys,
                profile_def.get("odds", {}),
                delimiter_feature,
            )
            if delimiter_values:
                return delimiter_values, [], True
            if delimiter_feature.get("fallback") == "separators":
                separator_candidates = build_separator_candidates(profile_def)
                return (
                    build_separator_values(
                        separator_candidates,
                        max(len(keys) - 1, 0),
                        order,
                        randomize=False,
                    ),
                    separator_candidates,
                    False,
                )
            return [], [], False

        if delimiter_feature.get("fallback") == "separators":
            separator_candidates = build_separator_candidates(profile_def)
            return (
                build_separator_values(
                    separator_candidates,
                    max(len(keys) - 1, 0),
                    order,
                    randomize=False,
                ),
                separator_candidates,
                False,
            )

    separator_candidates = build_separator_candidates(profile_def)
    return (
        build_separator_values(
            separator_candidates,
            max(len(keys) - 1, 0),
            order,
            randomize=False,
        ),
        separator_candidates,
        False,
    )


def is_terminal_punctuation_enabled(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "enabled"
    return False


def build_prefix_value(profile_def: dict[str, Any], odds: dict[str, Any] | None = None) -> str:
    prefix_feature = profile_def.get("prefix")
    if not isinstance(prefix_feature, dict):
        legacy_prefix_source = profile_def.get("prefixes")
        prefix_odds = (
            odds.get("prefixes") if isinstance(odds, dict) and "prefixes" in odds else profile_def.get("odds", {}).get("prefixes", 0)
        )
        if isinstance(legacy_prefix_source, str):
            prefix_feature = {
                "enabled": True,
                "odds": prefix_odds,
                "files": {"prefixes": legacy_prefix_source},
                "values": [],
            }
        elif isinstance(legacy_prefix_source, list):
            prefix_feature = {
                "enabled": True,
                "odds": prefix_odds,
                "files": {},
                "values": legacy_prefix_source,
            }
        else:
            return ""
    return build_feature_value(prefix_feature).strip()


def build_terminal_punctuation(
    profile_def: dict[str, Any], odds: dict[str, Any] | None = None,
) -> str:
    terminal_feature = profile_def.get("terminal-punctuation")
    if isinstance(terminal_feature, dict):
        return build_feature_value(terminal_feature)
    if not is_terminal_punctuation_enabled(terminal_feature):
        return ""
    terminal_odds = (
        odds.get("terminal-punctuation")
        if isinstance(odds, dict) and "terminal-punctuation" in odds
        else profile_def.get("odds", {}).get("terminal-punctuation", 0)
    )
    terminal_feature = {
        "enabled": True,
        "odds": terminal_odds,
        "files": {"terminal-punctuation": "common/terminal-punctuations.json"},
        "values": [],
    }
    return build_feature_value(terminal_feature)


def normalize_separators(spec: Any) -> list[str]:
    if not isinstance(spec, list):
        message = "separators must be a list"
        raise TypeError(message)

    separators: list[str] = []
    for separator_value in spec:
        if not isinstance(separator_value, str):
            message = "separators must contain strings only"
            raise TypeError(message)
        separators.append(separator_value)

    unique: list[str] = []
    for separator in separators:
        if separator not in unique:
            unique.append(separator)
    return unique


def normalize_separators_feature_spec(spec: Any) -> dict[str, Any]:
    if isinstance(spec, list):
        return {"enabled": True, "odds": 100, "files": {}, "values": spec}
    if isinstance(spec, dict):
        return spec
    raise TypeError("separators must be an object or list")


def build_separator_values(
    separators: list[str],
    count: int,
    order: str,
    randomize: bool = False,
) -> list[str]:
    if not separators:
        return []
    if len(separators) == 1:
        return [separators[0]] * max(count, 0)
    if randomize:
        return [random_generator.choice(separators) for _ in range(max(count, 0))]
    return [separators[i % len(separators)] for i in range(max(count, 0))]


def order_profile_keys(keys: list[str], order: str) -> list[str]:
    normalized = order.strip().lower() if isinstance(order, str) else "normal"
    if normalized == "random":
        result = keys.copy()
        random_generator.shuffle(result)
        return result
    if normalized == "normal":
        return keys.copy()
    message = "order must be one of: normal, random"
    raise ValueError(message)


def list_from_name(list_name: str, language: str | None = None) -> list[str] | None:
    stable_name = normalize_path(list_name)
    if not stable_name:
        return None

    if ".." in stable_name:
        message = f"Invalid list token: {stable_name}"
        raise ValueError(message)

    if "*" in stable_name:
        values: list[str] = []

        for base_root in [DATA_DIR, CATALOG_DIR]:
            for candidate in sorted(base_root.glob(stable_name)):
                if candidate.is_file():
                    loaded = load_json_file(candidate)
                    if isinstance(loaded, list):
                        values.extend(loaded)

        if values:
            return values

        if stable_name.endswith("/*"):
            prefix = stable_name[:-2]
            for base_root in [DATA_DIR, CATALOG_DIR]:
                alternate = base_root / f"{prefix}.json"
                if alternate.exists() and alternate.is_file():
                    loaded = load_json_file(alternate)
                    if isinstance(loaded, list):
                        values.extend(loaded)

        return values or None

    if not stable_name.endswith(".json"):
        return None

    candidate_paths: list[Path] = [
        DATA_DIR / stable_name,
        DATA_DIR / "categories" / stable_name,
        CATALOG_DIR / stable_name,
        CATALOG_DIR / "categories" / stable_name,
    ]

    for candidate in candidate_paths:
        if candidate.exists():
            loaded = load_json_file(candidate)
            if isinstance(loaded, list):
                return loaded
        alternate = candidate.with_suffix("")
        if alternate.exists() and alternate.is_file():
            loaded = load_json_file(alternate)
            if isinstance(loaded, list):
                return loaded

    return None


def tokenize_expression(expr: str) -> list[str]:
    """Tokenizes an expression into parts.

    Args:
        expr: Expression string to tokenize.

    Returns:
        List of tokens.
    """
    parts = re.split(r"([@\-\|\+]+)", expr)
    tokens = []
    for part in parts:
        if part == "":
            continue
        if re.fullmatch(r"[@\-\|\+]+", part):
            tokens.append(part)
            continue
        # Keep . as separator only when token is not a path (no slash)
        if "." in part and "/" not in part:
            subparts = re.split(r"(\.)", part)
            tokens.extend([s for s in subparts if s != ""])
        else:
            tokens.append(part)
    return tokens


def render_expression(expr: str) -> str:
    """Renders an expression by replacing tokens with random values.

    Args:
        expr: Expression string.

    Returns:
        Rendered string.

    Raises:
        ValueError: If an unknown token is encountered.
    """
    tokens = tokenize_expression(expr)
    output = []
    for token in tokens:
        if re.fullmatch(r"[@\-\.\|\+]+", token):
            output.append(token)
            continue

        values = list_from_name(token)
        if values is None:
            message = f"Unknown list token: '{token}' in expression '{expr}'"
            raise ValueError(message)

        output.append(str(random_generator.choice(values)))
    return "".join(output)


def render_parts(parts: Any) -> str:
    """Renders a list of parts by replacing tokens with random values.

    Args:
        parts: List of string tokens.

    Returns:
        Rendered string.

    Raises:
        ValueError: If parts is not a list or contains non-string items.
    """
    if not isinstance(parts, list):
        message = "parts must be a list"
        raise TypeError(message)
    output = []
    for item in parts:
        if not isinstance(item, str):
            message = "parts must contain string tokens only"
            raise TypeError(message)
        if re.fullmatch(r"[@\-\.\|\+]+", item):
            output.append(item)
            continue
        values = list_from_name(item)
        if values is None:
            message = f"Unknown list token: '{item}' in parts"
            raise ValueError(message)
        output.append(str(random_generator.choice(values)))
    return "".join(output)


def render_template(template: str) -> str:
    """Renders a template by replacing placeholders with random values.

    Args:
        template: Template string with {token} placeholders.

    Returns:
        Rendered string.

    Raises:
        ValueError: If an unknown token is encountered.
    """

    def replacement(match: re.Match[str]) -> str:
        key = match.group(1)
        values = list_from_name(key)
        if values is None:
            message = f"Unknown template token: '{{{key}}}'"
            raise ValueError(message)
        return str(random_generator.choice(values))

    return re.sub(r"\{([^}]+)\}", replacement, template)


def render_profile_definition(
    profile_def: dict[str, Any], order: str = "normal",
) -> str:
    """Renders a profile definition into a passphrase.

    Args:
        profile_def: Dictionary with profile settings.
        order: Generation order override.

    Returns:
        Rendered passphrase string.

    Raises:
        ValueError: If profile definition is invalid.
    """
    return str(build_generation_context(profile_def, order)["rendered"])


def build_generation_context(
    profile_def: Any, order: str = "normal",
) -> dict[str, Any]:
    if not isinstance(profile_def, dict):
        message = "Profile definition must be an object with files"
        raise TypeError(message)

    unsupported_keys = [
        key
        for key in profile_def
        if key not in {
            "files",
            "separators",
            "delimiters",
            "prefix",
            "prefixes",
            "terminal-punctuation",
            "space",
            "odds",
            "agents",
        }
    ]
    if unsupported_keys:
        message = "Unsupported profile keys: " + ", ".join(
            sorted(unsupported_keys),
        )
        raise ValueError(message)

    files = resolve_profile_files(profile_def.get("files"))
    if not isinstance(files, dict) or not files:
        message = 'Profile object must contain "files" with at least one entry'
        raise ValueError(message)

    raw_separators_spec = profile_def.get("separators")
    separators_spec = normalize_separators_feature_spec(raw_separators_spec)
    profile_def["separators"] = separators_spec

    keys = order_profile_keys(list(files.keys()), order)

    requested_parts: list[str] = []
    values_by_key: dict[str, str] = {}
    for token in keys:
        source = files[token]
        if not isinstance(source, str):
            message = "file references must be string list tokens or paths"
            raise TypeError(message)
        values = list_from_name(source)
        if values is None:
            message = f"Unknown list token/path: '{source}' in profile files"
            raise ValueError(message)
        selected_value = str(random_generator.choice(values))
        requested_parts.append(selected_value)
        values_by_key[token] = selected_value

    separator_values, separator_candidates, used_delimiters = build_separator_values_for_profile(
        profile_def,
        keys,
        order,
        randomize=True,
    )

    rendered_parts: list[str] = []
    for i, part in enumerate(requested_parts):
        rendered_parts.append(part)
        if i < len(separator_values):
            rendered_parts.append(separator_values[i])

    strict_render = "".join(rendered_parts)

    prefix_value = build_prefix_value(profile_def)
    punctuation_value = build_terminal_punctuation(profile_def)

    rendered = strict_render
    if prefix_value:
        rendered = f"{prefix_value} {rendered}"
    if punctuation_value:
        rendered = rendered.rstrip(" ") + punctuation_value

    base_entropy = estimate_selection_entropy(keys, files)
    order_entropy = estimate_order_entropy(keys, order)
    separator_entropy = (
        estimate_delimiter_entropy(keys)
        if used_delimiters
        else math.log2(len(separator_candidates)) if separator_candidates else 0.0
    )
    prefix_entropy = estimate_prefix_entropy(profile_def)
    punctuation_entropy = estimate_terminal_punctuation_entropy(profile_def)
    actual_entropy = (
        base_entropy
        + order_entropy
        + separator_entropy
        + prefix_entropy
        + punctuation_entropy
    )

    return {
        "rendered": rendered,
        "profile_def": profile_def,
        "files": files,
        "selected_keys": keys,
        "profile_order": keys,
        "values_by_key": values_by_key,
        "separators": separator_candidates,
        "separators_spec": raw_separators_spec,
        "order": order,
        "fields_spec": "all",
        "requested_parts": requested_parts,
        "separator_values": separator_values,
        "strict_render": strict_render,
        "prefix": prefix_value,
        "terminal_punctuation": punctuation_value,
        "base_entropy": base_entropy,
        "order_entropy": order_entropy,
        "separator_entropy": separator_entropy,
        "prefix_entropy": prefix_entropy,
        "punctuation_entropy": punctuation_entropy,
        "actual_entropy": actual_entropy,
        "strict_entropy": estimate_profile_definition_entropy(profile_def),
    }


def estimate_expression_entropy(expr: str) -> float:
    """Estimates the entropy of an expression.

    Args:
        expr: Expression string.

    Returns:
        Entropy in bits.
    """
    bits = 0.0
    tokens = tokenize_expression(expr)
    for token in tokens:
        if re.fullmatch(r"[@\-\.\|\+]+", token):
            continue
        values = list_from_name(token)
        if values:
            try:
                n = len(values)
            except TypeError:
                n = 1
            if n > 0:
                bits += math.log2(n)
    return bits


def estimate_parts_entropy(parts: list[str]) -> float:
    """Estimates the entropy of a list of parts.

    Args:
        parts: List of string tokens.

    Returns:
        Entropy in bits.
    """
    bits = 0.0
    for item in parts:
        if re.fullmatch(r"[@\-\.\|\+]+", item):
            continue
        values = list_from_name(item)
        if values:
            try:
                n = len(values)
            except TypeError:
                n = 1
            if n > 0:
                bits += math.log2(n)
    return bits


def estimate_template_entropy(template: str) -> float:
    """Estimates the entropy of a template.

    Args:
        template: Template string.

    Returns:
        Entropy in bits.
    """
    bits = 0.0
    for match in re.finditer(r"{([^}]+)}", template):
        key = match.group(1)
        values = list_from_name(key)
        if values:
            try:
                n = len(values)
            except TypeError:
                n = 1
            if n > 0:
                bits += math.log2(n)
    return bits


def estimate_selection_entropy(
    selected_keys: list[str], files: dict[str, Any], language: str | None = None,
) -> float:
    bits = 0.0
    for key in selected_keys:
        source = files.get(key)
        if not isinstance(source, str):
            message = "file references must be string list tokens or paths"
            raise TypeError(message)
        values = list_from_name(source, language=language)
        if values is None:
            message = f"Unknown list token/path: '{source}'"
            raise ValueError(message)
        n = len(values) if hasattr(values, "__len__") else 1
        if n > 0:
            bits += math.log2(n)
    return bits


def estimate_order_entropy(selected_keys: list[str], order_spec: str) -> float:
    if order_spec != "random" or len(selected_keys) < MIN_ORDER_ENTRIES:
        return 0.0
    return math.log2(math.factorial(len(selected_keys)))


def estimate_delimiter_entropy(keys: list[str]) -> float:
    entropy = 0.0
    for left, right in zip(keys, keys[1:]):
        file_name = delimiter_file_name(left, right)
        values = load_delimiter_values(file_name)
        n = len(values) if hasattr(values, "__len__") else 1
        if n > 0:
            entropy += math.log2(n)
    return entropy


def estimate_prefix_entropy(profile_def: dict[str, Any]) -> float:
    prefix_feature = profile_def.get("prefix")
    if isinstance(prefix_feature, dict):
        values = build_feature_candidates(prefix_feature)
        n = len(values) if hasattr(values, "__len__") else 1
        return math.log2(n) if n > 0 else 0.0
    return 0.0


def estimate_terminal_punctuation_entropy(profile_def: dict[str, Any]) -> float:
    terminal_feature = profile_def.get("terminal-punctuation")
    if isinstance(terminal_feature, dict) and terminal_feature.get("enabled", False):
        values = build_feature_candidates(terminal_feature)
        n = len(values) if hasattr(values, "__len__") else 1
        return math.log2(n) if n > 0 else 0.0
    return 0.0


def estimate_separator_entropy(
    separators_spec: Any,
    count: int = 0,
    order_spec: str = "normal",
    field_keys: list[str] | None = None,
) -> float:
    if isinstance(separators_spec, dict):
        return 0.0

    separators = normalize_separators(
        separators_spec if separators_spec is not None else [],
    )
    if len(separators) <= 1:
        return 0.0
    normalized = (
        order_spec.strip().lower() if isinstance(order_spec, str) else "normal"
    )
    if normalized in {"random", "normal"}:
        return math.log2(len(separators))
    message = "order must be one of: normal, random"
    raise ValueError(message)


def estimate_profile_definition_entropy(
    profile_def: dict[str, Any],
    order: str = "normal",
) -> float:
    """Estimates the entropy of a profile definition.

    Args:
        profile_def: Profile definition dictionary.
        order: Order mode, either 'normal' or 'random'.

    Returns:
        Entropy in bits.

    Raises:
        ValueError: If profile definition is invalid.
    """
    if not isinstance(profile_def, dict) or "files" not in profile_def:
        message = "Profile definition must be a dict with files"
        raise ValueError(message)

    unsupported_keys = [
        key
        for key in profile_def
        if key not in {
            "files",
            "separators",
            "delimiters",
            "prefix",
            "prefixes",
            "terminal-punctuation",
            "space",
            "odds",
            "agents",
        }
    ]
    if unsupported_keys:
        message = "Unsupported profile keys: " + ", ".join(
            sorted(unsupported_keys),
        )
        raise ValueError(message)

    files = resolve_profile_files(profile_def["files"])
    if not isinstance(files, dict) or not files:
        message = 'Profile object must contain "files" with at least one entry'
        raise ValueError(message)

    entropies: dict[str, float] = {}
    for key, source in files.items():
        if not isinstance(source, str):
            message = "file references must be string list tokens or paths"
            raise TypeError(message)
        values = list_from_name(source)
        if values is None:
            message = f"Unknown list token/path: '{source}' in profile files"
            raise ValueError(message)
        n = len(values) if hasattr(values, "__len__") else 1
        entropies[key] = math.log2(n) if n > 0 else 0.0

    entropy = sum(entropies.values())
    entropy += estimate_order_entropy(list(files.keys()), order)
    delimiters_spec = profile_def.get("delimiters")
    separators_spec = normalize_separators_feature_spec(profile_def.get("separators"))
    if isinstance(delimiters_spec, dict) and delimiters_spec.get("enabled", False):
        entropy += estimate_delimiter_entropy(list(files.keys()))
    elif isinstance(separators_spec, dict):
        separator_values: list[str] = []
        for feature_name in ("separators", "space"):
            feature_def = separators_spec if feature_name == "separators" else profile_def.get(feature_name)
            if isinstance(feature_def, dict) and feature_def.get("enabled", False):
                separator_values.extend(build_feature_candidates(feature_def))
        if separator_values:
            entropy += math.log2(len(separator_values))
    else:
        raise TypeError("separators must be an object")
    entropy += estimate_prefix_entropy(profile_def)
    entropy += estimate_terminal_punctuation_entropy(profile_def)
    return entropy


def classify_entropy(entropy_bits: float) -> str:
    """Classifies entropy level.

    Args:
        entropy_bits: Entropy in bits.

    Returns:
        Classification string.
    """
    if entropy_bits < VERY_LOW_ENTROPY:
        return "very low"
    if entropy_bits < LOW_ENTROPY:
        return "low"
    if entropy_bits < MEDIUM_ENTROPY:
        return "medium"
    if entropy_bits < HIGH_ENTROPY:
        return "high"
    return "very high"


def build_variation_context_from_saved_selection(
    base_context: dict[str, Any],
    order: str,
) -> dict[str, Any]:
    profile_def = base_context["profile_def"]
    files = base_context["files"]
    values_by_key = base_context["values_by_key"]
    separators = base_context["separators"]

    if order == "random" and base_context["order"] == "random":
        keys = base_context["selected_keys"]
    else:
        keys = order_profile_keys(list(files.keys()), order)

    requested_parts = [values_by_key[key] for key in keys]
    separator_values, separator_candidates, used_delimiters = build_separator_values_for_profile(
        profile_def,
        keys,
        order,
        randomize=True,
    )

    rendered_parts: list[str] = []
    for i, part in enumerate(requested_parts):
        rendered_parts.append(part)
        if i < len(separator_values):
            rendered_parts.append(separator_values[i])

    strict_render = "".join(rendered_parts)
    rendered = strict_render
    prefix_value = base_context.get("prefix", "")
    punctuation_value = base_context.get("terminal_punctuation", "")
    if prefix_value:
        rendered = f"{prefix_value} {rendered}"
    if punctuation_value:
        rendered = rendered.rstrip(" ") + punctuation_value

    base_entropy = estimate_selection_entropy(list(files.keys()), files)
    order_entropy = estimate_order_entropy(keys, order)
    separator_entropy = (
        estimate_delimiter_entropy(keys)
        if used_delimiters
        else math.log2(len(separator_candidates)) if separator_candidates else 0.0
    )
    prefix_entropy = estimate_prefix_entropy(profile_def)
    punctuation_entropy = estimate_terminal_punctuation_entropy(profile_def)
    actual_entropy = (
        base_entropy
        + order_entropy
        + separator_entropy
        + prefix_entropy
        + punctuation_entropy
    )

    return {
        "rendered": rendered,
        "profile_def": profile_def,
        "files": files,
        "selected_keys": keys,
        "profile_order": keys,
        "values_by_key": values_by_key,
        "separators": separators,
        "order": order,
        "fields_spec": "all",
        "requested_parts": requested_parts,
        "separator_values": separator_values,
        "strict_render": strict_render,
        "prefix": prefix_value,
        "terminal_punctuation": punctuation_value,
        "base_entropy": base_entropy,
        "order_entropy": order_entropy,
        "separator_entropy": separator_entropy,
        "prefix_entropy": prefix_entropy,
        "punctuation_entropy": punctuation_entropy,
        "actual_entropy": actual_entropy,
        "strict_entropy": estimate_profile_definition_entropy(profile_def),
    }


def format_generation_details(context: dict[str, Any]) -> str:
    profile = context.get("profile_def", {})
    separators_spec = context.get("separators_spec", profile.get("separators", context["separators"]))
    prefix_value = context.get("prefix", "")
    punctuation_value = context.get("terminal_punctuation", "")
    lines = [
        "Cognitive Passphrases Generator v0.6.1 - Details",
        f"  order: {context['order']}",
        f"  separators: {separators_spec}",
        f"  prefix: {prefix_value if prefix_value else 'none'}",
        f"  terminal punctuation: {punctuation_value if punctuation_value else 'none'}",
        "",
        f"  {'Field':<10} | {'Value':<34} | Separator",
        f"  {'-' * 10} | {'-' * 34} | {'-' * 9}",
    ]
    detail_keys = context["selected_keys"]

    for index, key in enumerate(detail_keys):
        value = context["values_by_key"].get(key, "")
        separator = ""
        if index < len(context["separator_values"]):
            separator = context["separator_values"][index]
        separator_display = f"'{separator}'" if separator else ""
        lines.append(f"  {key:<10} | {value:<34} | {separator_display}")

    lines.extend(
        [
            "",
            f"  Base entropy: {context['base_entropy']:.2f} bits ({classify_entropy(context['base_entropy'])})",
            f"  Order entropy: {context['order_entropy']:.2f} bits ({classify_entropy(context['order_entropy'])})",
            f"  Separator entropy: {context['separator_entropy']:.2f} bits ({classify_entropy(context['separator_entropy'])})",
            f"  Actual entropy: {context['actual_entropy']:.2f} bits ({classify_entropy(context['actual_entropy'])})",
            "",
            "  output     | Entropy level | passphrase",
            "  ---------- | ------------- | ----------",
        ],
    )

    for label, order_name in [
        ("normal", "normal"),
        ("random", "random"),
    ]:
        detail_context = build_variation_context_from_saved_selection(
            context,
            order_name,
        )
        lines.append(
            f"  {label:<10} | {detail_context['actual_entropy']:>13.2f} | {detail_context['strict_render']}",
        )

    return "\n".join(lines)


def main() -> None:
    """Main entry point for the passphrase generator."""
    parser = argparse.ArgumentParser(
        description="Generate passphrases using profiles.json patterns.",
    )
    parser.add_argument(
        "profile",
        nargs="?",
        help="Profile name defined in profiles.json",
    )
    parser.add_argument(
        "--profile",
        "-p",
        dest="profile",
        help="Profile name defined in profiles.json",
    )
    parser.add_argument(
        "--count",
        "-n",
        type=int,
        default=1,
        help="How many passphrases to generate",
    )
    parser.add_argument(
        "--details",
        "-d",
        action="store_true",
        help="Show generation details such as fields, separators, and punctuation",
    )
    parser.add_argument(
        "--random",
        dest="order",
        action="store_const",
        const="random",
        help="Use random field order instead of normal order",
    )
    parser.add_argument(
        "--ai",
        dest="ai_key",
        help="Reserved for future AI augmentation; currently not implemented",
    )
    parser.add_argument(
        "--ai-language",
        default="en-us",
        help="Reserved for future AI augmentation language target",
    )

    if len(sys.argv) == 1:
        print("=== xSpace Passphrase Generator ===")
        print("Run from PowerShell/cmd with:")
        print("  python generate_passphrase.py xspace --count 1")
        print("")
        print("Usage: python generate_passphrase.py PROFILE [--count N] [--details] [--random]")
        print("Example: python generate_passphrase.py xspace --count 2 --random")
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    if args.profile is None:
        parser.error("the following arguments are required: profile")

    from profiles import collect_profiles_validation_results

    try:
        raw_profiles, invalid_profiles = collect_profiles_validation_results(PROFILE_FILE)
    except (ValueError, FileNotFoundError, TypeError) as ex:
        message = f"Validation failed while scanning profiles file: {ex}"
        raise SystemExit(message) from ex

    profiles = {k.lower(): v for k, v in raw_profiles.items()}
    profile_name = args.profile.lower()
    if profile_name not in profiles:
        message = f'Error: profile "{args.profile}" not found in {PROFILE_FILE}'
        raise SystemExit(message)

    if invalid_profiles:
        print("Warning: some profiles in profiles.json are invalid and will be skipped:")
        for invalid_name, error_text in invalid_profiles.items():
            print(f"  - {invalid_name}: {error_text}")

        if sys.stdin.isatty():
            answer = input("Continue using only validated profiles? [y/N] ").strip().lower()
            if answer not in {"y", "yes"}:
                raise SystemExit("Aborted due to invalid profile definitions.")
        else:
            raise SystemExit(
                "Profiles file contains invalid definitions. Re-run interactively to confirm continuing or fix the listed errors.",
            )

    profile_def = profiles[profile_name]

    order = "normal"
    if args.order == "random":
        order = "random"

    if args.ai_key:
        print(
            "Warning: --ai is reserved for future AI integration and has no effect at this time.",
        )

    entropy_bits = estimate_profile_definition_entropy(profile_def, order)
    entropy_label = classify_entropy(entropy_bits)

    print(
        f"Cognitive Passphrases Generator - Actual Entropy level [{entropy_bits:.2f}] ({entropy_label})",
    )

    for _ in range(args.count):
        if args.details:
            context = build_generation_context(profile_def, order)
            print(format_generation_details(context))
            print()
            print(context["rendered"])
        else:
            print(render_profile_definition(profile_def, order))


if __name__ == "__main__":
    main()
