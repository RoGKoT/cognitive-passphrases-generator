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
        v = os.path.expandvars(v)
        variables[k] = v
    return variables


_path_vars = load_paths_env(DATA_DIR / "paths.env")
PROFILE_DIR = Path(_path_vars.get("PROFILES", DATA_DIR / "profiles"))
PROFILE_FILE = PROFILE_DIR / "profiles.json"
CATALOG_DIR = Path(_path_vars.get("CATALOG", DATA_DIR / "catalog"))

random_generator = random.SystemRandom()


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
        return json.loads(text)
    except json.JSONDecodeError:
        profiles = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            profiles[key.strip()] = value.strip()
        return profiles


def normalize_path(path: str) -> str:
    normalized = path.strip()
    if normalized.startswith("/"):
        normalized = normalized[1:]
    return normalized


def load_json_file(path: Path) -> Any | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
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


def load_dict_file(path: Path) -> dict[str, Any]:
    values = load_json_file(path)
    if isinstance(values, dict):
        return values
    return {}


def load_vocabulary_resource(name: str) -> Any | None:
    return load_json_file(CATALOG_DIR / "common" / "vocabulary" / name)


def format_phrase(value: str, key: str, grammar: dict[str, Any]) -> str:
    if not value:
        return ""
    article = grammar.get("articles", {}).get(key)
    if article:
        normalized = value.strip()
        if normalized.lower().startswith(f"{article.lower()} "):
            return normalized
        return f"{article} {normalized}"
    return value


def apply_preposition(value: str, key: str, grammar: dict[str, Any]) -> str:
    if not value:
        return ""
    preposition = grammar.get("prepositions", {}).get(key)
    if preposition:
        normalized = value.strip()
        first_word = normalized.split()[0].lower()
        known_prepositions = {
            "at",
            "in",
            "on",
            "before",
            "after",
            "during",
            "since",
            "until",
            "while",
            "when",
            "by",
            "near",
            "nearby",
            "within",
            "as",
            "throughout",
            "once",
        }
        if first_word == preposition.lower() or first_word in known_prepositions:
            return normalized
        return f"{preposition} {normalized}"
    return value


def pick_modifier(name: str, modifiers: dict[str, Any]) -> str:
    values = modifiers.get(name)
    if isinstance(values, list) and values:
        return random_generator.choice(values)
    return ""


def parse_simple_list_file(path: Path) -> list[str] | None:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return None
    values: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line in {"[", "]"}:
            continue
        if line.endswith(','):
            line = line[:-1].rstrip()
        if line.startswith('"') and line.endswith('"'):
            values.append(line[1:-1])
            continue
        return None
    return values


def resolve_profile_source_files(source_reference: str) -> dict[str, str]:
    if "#" not in source_reference:
        raise ValueError(
            f"Invalid profile source reference: '{source_reference}'"
        )

    ref_path, key = source_reference.split("#", 1)
    ref_path = normalize_path(ref_path)
    source_file = PROFILE_DIR / ref_path
    if not source_file.exists():
        source_file = DATA_DIR / ref_path

    data = load_json_file(source_file)
    if data is None or not isinstance(data, dict):
        raise FileNotFoundError(
            f"Unable to load profile source '{ref_path}' from {source_file}"
        )

    if key not in data:
        raise ValueError(f"Source key '{key}' not found in {source_file}")

    profile_data = data[key]
    if not isinstance(profile_data, dict) or "files" not in profile_data:
        raise ValueError(
            f"Source '{source_reference}' must contain a 'files' object"
        )

    if not isinstance(profile_data["files"], dict):
        raise ValueError(
            f"'files' in source '{source_reference}' must be an object"
        )

    return profile_data["files"]


def resolve_profile_files(files_spec: Any) -> dict[str, str]:
    if isinstance(files_spec, dict):
        return files_spec
    if isinstance(files_spec, str):
        return resolve_profile_source_files(files_spec)
    raise ValueError("files must be either an object or a source reference string")


def load_all_separators() -> list[str]:
    candidate_paths = [
        CATALOG_DIR / "common" / "vocabulary" / "separators.json",
        CATALOG_DIR / "common" / "vocabulary" / "separators",
    ]
    for candidate in candidate_paths:
        if not candidate.exists():
            continue
        separators = load_json_file(candidate)
        if isinstance(separators, list):
            return separators
        parsed = parse_simple_list_file(candidate)
        if isinstance(parsed, list):
            return parsed
    raise FileNotFoundError(
        "Could not load separators from catalog/common/vocabulary/separators"
    )


def normalize_separators(spec: Any) -> list[str]:
    if isinstance(spec, str):
        if spec == "all":
            return load_all_separators()
        raise ValueError("separators must be a list or 'all'")

    if not isinstance(spec, list):
        raise ValueError("separators must be a list or 'all'")

    separators: list[str] = []
    for token in spec:
        if not isinstance(token, str):
            raise ValueError("separators must contain strings only")
        if token == "all":
            separators.extend(load_all_separators())
        else:
            separators.append(token)

    unique: list[str] = []
    for separator in separators:
        if separator not in unique:
            unique.append(separator)
    return unique


def normalize_order(order_spec: Any) -> str:
    if order_spec is None:
        return "strict"
    if not isinstance(order_spec, str):
        raise ValueError("order must be a string")
    normalized = order_spec.strip().lower()
    if normalized == "lock":
        return "strict"
    if normalized not in {"random", "ascending", "descending", "strict"}:
        raise ValueError(
            "order must be one of: random, ascending, descending, strict"
        )
    return normalized


def normalize_language(language_spec: Any) -> str:
    if language_spec is None:
        return "all"
    if not isinstance(language_spec, str):
        raise ValueError("language must be a string")
    return language_spec.strip().lower() or "all"


def normalize_output(output_spec: Any) -> str:
    if output_spec is None:
        return "strict"
    if not isinstance(output_spec, str):
        raise ValueError("output must be a string")
    normalized = output_spec.strip().lower()
    if normalized == "ai":
        normalized = "ai sentence"
    if normalized not in {"readable sentence", "ai sentence", "strict"}:
        raise ValueError("output must be 'readable sentence', 'ai sentence', or 'strict'")
    return normalized


def normalize_terminal_punctuation(punctuation_spec: Any) -> str:
    if punctuation_spec is None:
        return "strict"
    if not isinstance(punctuation_spec, str):
        raise ValueError("terminal-punctuation must be a string")
    normalized = punctuation_spec.strip().lower()
    if normalized not in {"sentence mood", "none", "random", "strict"}:
        raise ValueError(
            "terminal-punctuation must be one of: sentence mood, none, random, strict"
        )
    return normalized


def normalize_marked_syntax(spec: Any) -> list[str]:
    syntax_styles = load_json_file(DATA_DIR / "marked-syntax.json")
    if not isinstance(syntax_styles, dict):
        return []
    valid_styles = set(syntax_styles.get("syntax_styles", {}).keys())
    if isinstance(spec, str):
        if spec == "all":
            return sorted(valid_styles)
        normalized = spec.strip()
        if normalized in valid_styles:
            return [normalized]
        raise ValueError(f"Unknown marked-syntax style: '{spec}'")
    if isinstance(spec, list):
        styles: list[str] = []
        for item in spec:
            if not isinstance(item, str):
                raise ValueError("marked-syntax list must contain strings only")
            normalized = item.strip()
            if normalized not in valid_styles:
                raise ValueError(f"Unknown marked-syntax style: '{item}'")
            if normalized not in styles:
                styles.append(normalized)
        return styles
    raise ValueError("marked-syntax must be a string or list of strings")


def apply_marked_syntax(text: str, syntax_styles: list[str]) -> str:
    if not syntax_styles:
        return text
    return text


def apply_terminal_punctuation(text: str, mode: str) -> str:
    if mode == "none":
        return re.sub(r"[.!?]+$", "", text)
    if mode == "strict":
        return text
    if mode == "random":
        if re.search(r"[.!?]$", text):
            return text
        return text + random_generator.choice([".", "!", "?"])
    if mode == "sentence mood":
        if re.search(r"[.!?]$", text):
            return text
        if re.match(r"(?i)^(who|what|where|when|why|how)\b", text):
            return text + "?"
        return text + "."
    return text


def human_join(items: list[str], conjunction: str = "and") -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} {conjunction} {items[1]}"
    return ", ".join(items[:-1]) + f", {conjunction} {items[-1]}"


def build_readable_sentence(
    selected_keys: list[str],
    values_by_key: dict[str, str],
    ai_mode: bool = False,
) -> str:
    grammar = load_dict_file(CATALOG_DIR / "common" / "vocabulary" / "grammar.json")
    modifiers = {}
    if ai_mode:
        modifiers = load_dict_file(CATALOG_DIR / "common" / "vocabulary" / "phrase_modifiers.json")
    templates = load_list_file(CATALOG_DIR / "common" / "vocabulary" / "sentence_templates.json")

    people_fields = ["actors", "characters", "heroes"]
    people = [values_by_key[k] for k in people_fields if k in values_by_key]
    subject = human_join(people, "and") or grammar.get("default_subject", "Someone")

    title = values_by_key.get("titles", "")
    title = format_phrase(title, "object", grammar)

    action = values_by_key.get("actions", "")
    verb = action or grammar.get("default_verb", "encounters")
    if ai_mode:
        action_modifier = pick_modifier("action_modifiers", modifiers)
        if action_modifier:
            verb = f"{action_modifier} {verb}"

    location = values_by_key.get("locations", "")
    location = apply_preposition(location, "location", grammar)
    if ai_mode and location:
        location_modifier = pick_modifier("location_modifiers", modifiers)
        if location_modifier:
            location = f"{location_modifier} {location}"

    timestamp = values_by_key.get("timestamps", "")
    if ai_mode:
        timestamp_modifier = pick_modifier("timestamp_modifiers", modifiers)
        if timestamp_modifier:
            timestamp = f"{timestamp_modifier} {timestamp}".strip()
    timestamp = apply_preposition(timestamp, "timestamp", grammar)

    prefix = ""
    if ai_mode:
        prefix = pick_modifier("sentence_prefixes", modifiers)

    object_value = title or grammar.get("default_object", "a mystery")
    template = random_generator.choice(templates) if templates else "{prefix}{subject} {verb} {object} {location} {timestamp}"

    sentence = template.format(
        prefix=prefix,
        subject=subject,
        verb=verb,
        object=object_value,
        location=location,
        timestamp=timestamp,
        modifier=pick_modifier("action_modifiers", modifiers) if ai_mode else "",
    )
    sentence = re.sub(r"\s+", " ", sentence).strip()
    if sentence and not re.search(r"[.!?]$", sentence):
        sentence += "."
    return sentence


def apply_output_format(text: str, mode: str) -> str:
    if mode not in {"readable sentence", "ai sentence", "strict"}:
        raise ValueError("Unknown output mode")
    return text


def select_fields(keys: list[str], fields_spec: Any, order_spec: str) -> list[str]:
    if fields_spec is None or fields_spec == "all":
        selected = keys.copy()
    elif isinstance(fields_spec, int):
        if fields_spec <= 0:
            raise ValueError("fields must be a positive integer or 'all'")
        count = min(fields_spec, len(keys))
        if order_spec == "random":
            selected = random_generator.sample(keys, count)
        elif order_spec == "ascending":
            selected = sorted(keys)[:count]
        elif order_spec == "descending":
            selected = sorted(keys, reverse=True)[:count]
        else:
            selected = keys[:count]
    elif isinstance(fields_spec, list):
        selected = []
        for item in fields_spec:
            if isinstance(item, int):
                index = item - 1
                if index < 0 or index >= len(keys):
                    raise ValueError("fields list contains invalid numeric index")
                key = keys[index]
            elif isinstance(item, str) and item.isdigit():
                index = int(item) - 1
                if index < 0 or index >= len(keys):
                    raise ValueError("fields list contains invalid numeric index")
                key = keys[index]
            elif isinstance(item, str):
                if item not in keys:
                    raise ValueError(f"Unknown field name: '{item}'")
                key = item
            else:
                raise ValueError("fields list must contain strings or integers")
            if key not in selected:
                selected.append(key)
    else:
        raise ValueError("fields must be 'all', a positive integer, or a list")

    if order_spec == "random" and isinstance(fields_spec, list):
        random_generator.shuffle(selected)
    elif order_spec == "ascending":
        selected = sorted(selected)
    elif order_spec == "descending":
        selected = sorted(selected, reverse=True)
    return selected


def list_from_name(list_name: str, language: str | None = None) -> list[str] | None:
    stable_name = normalize_path(list_name)
    if not stable_name:
        return None

    if ".." in stable_name:
        raise ValueError(f"Invalid list token: {stable_name}")

    if stable_name.endswith("/*"):
        prefix = stable_name[:-2]
        values: list[str] = []

        for base in [DATA_DIR / prefix, CATALOG_DIR / prefix]:
            if base.exists() and base.is_dir():
                if language and language != "all":
                    candidate = base / f"{language}.json"
                    if candidate.exists():
                        values = load_json_file(candidate)
                        if isinstance(values, list):
                            return values
                for file in sorted(base.glob("*.json")):
                    parsed = load_json_file(file)
                    if isinstance(parsed, list):
                        values.extend(parsed)

        for base_parent in [DATA_DIR / "categories", CATALOG_DIR / "categories"]:
            candidate_dir = base_parent / prefix
            if candidate_dir.exists() and candidate_dir.is_dir():
                if language and language != "all":
                    specific = candidate_dir / f"{language}.json"
                    if specific.exists():
                        values = load_json_file(specific)
                        if isinstance(values, list):
                            return values
                for file in sorted(candidate_dir.glob("*.json")):
                    parsed = load_json_file(file)
                    if isinstance(parsed, list):
                        values.extend(parsed)

        return values if values else None

    if not stable_name.endswith(".json"):
        return None

    candidate_paths = [
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
            parsed = parse_simple_list_file(candidate)
            if isinstance(parsed, list):
                return parsed
        alternate = candidate.with_suffix("")
        if alternate.exists() and alternate.is_file():
            loaded = load_json_file(alternate)
            if isinstance(loaded, list):
                return loaded
            parsed = parse_simple_list_file(alternate)
            if isinstance(parsed, list):
                return parsed

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
            raise ValueError(f"Unknown list token: '{token}' in expression '{expr}'")

        output.append(str(random_generator.choice(values)))
    return "".join(output)


def render_parts(parts: list[str]) -> str:
    """Renders a list of parts by replacing tokens with random values.

    Args:
        parts: List of string tokens.

    Returns:
        Rendered string.

    Raises:
        ValueError: If parts is not a list or contains non-string items.
    """
    if not isinstance(parts, list):
        raise ValueError("parts must be a list")
    output = []
    for item in parts:
        if not isinstance(item, str):
            raise ValueError("parts must contain string tokens only")
        if re.fullmatch(r"[@\-\.\|\+]+", item):
            output.append(item)
            continue
        values = list_from_name(item)
        if values is None:
            raise ValueError(f"Unknown list token: '{item}' in parts")
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

    def replacement(match):
        key = match.group(1)
        values = list_from_name(key)
        if values is None:
            raise ValueError(f"Unknown template token: '{{{key}}}'")
        return str(random_generator.choice(values))

    return re.sub(r"\{([^}]+)\}", replacement, template)


def render_profile_definition(profile_def: dict[str, Any]) -> str:
    """Renders a profile definition into a passphrase.

    Args:
        profile_def: Dictionary with profile settings.

    Returns:
        Rendered passphrase string.

    Raises:
        ValueError: If profile definition is invalid.
    """
    if not isinstance(profile_def, dict):
        raise ValueError("Profile definition must be an object with files")

    files = resolve_profile_files(profile_def.get("files"))
    if not isinstance(files, dict) or not files:
        raise ValueError('Profile object must contain "files" with at least one entry')

    separators = normalize_separators(profile_def.get("separators", []))
    language = normalize_language(profile_def.get("language"))
    order = normalize_order(profile_def.get("order"))
    fields_spec = profile_def.get("fields", "all")
    output_mode = normalize_output(profile_def.get("output"))
    terminal_punctuation = normalize_terminal_punctuation(
        profile_def.get("terminal-punctuation")
    )
    marked_syntax_styles = normalize_marked_syntax(profile_def.get("marked-syntax", "all"))

    keys = list(files.keys())
    selected_keys = select_fields(keys, fields_spec, order)

    requested_parts: list[str] = []
    for token in selected_keys:
        source = files[token]
        if not isinstance(source, str):
            raise ValueError("file references must be string list tokens or paths")
        values = list_from_name(source, language=language)
        if values is None:
            raise ValueError(f"Unknown list token/path: '{source}' in profile files")
        requested_parts.append(str(random_generator.choice(values)))

    separator_values: list[str] = []
    if separators:
        if len(separators) == 1:
            separator_values = [separators[0]] * max(len(requested_parts) - 1, 0)
        else:
            separator_values = [
                separators[i % len(separators)]
                for i in range(max(len(requested_parts) - 1, 0))
            ]

    result_parts: list[str] = []
    for i, part in enumerate(requested_parts):
        result_parts.append(part)
        if i < len(separator_values):
            result_parts.append(separator_values[i])

    rendered = "".join(result_parts)
    if output_mode in {"readable sentence", "ai sentence"}:
        values_by_key = {token: requested_parts[i] for i, token in enumerate(selected_keys)}
        rendered = build_readable_sentence(
            selected_keys,
            values_by_key,
            ai_mode=(output_mode == "ai sentence"),
        )
        rendered = apply_terminal_punctuation(rendered, terminal_punctuation)
    else:
        rendered = apply_marked_syntax(rendered, marked_syntax_styles)
        rendered = apply_terminal_punctuation(rendered, terminal_punctuation)
    return apply_output_format(rendered, output_mode)


def estimate_expression_entropy(expr: str) -> float:
    """Estimates the entropy of an expression.

    Args:
        expr: Expression string.

    Returns:
        Entropy in bits.

    Raises:
        TypeError: If expression is not a string.
    """
    if not isinstance(expr, str):
        msg = "Expression entropy can only be calculated for string expressions"
        raise TypeError(msg)

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

    Raises:
        TypeError: If parts is not a list or contains non-strings.
    """
    if not isinstance(parts, list):
        msg = "Parts entropy can only be calculated for list parts"
        raise TypeError(msg)

    bits = 0.0
    for item in parts:
        if not isinstance(item, str):
            msg = "Parts must contain string tokens only"
            raise TypeError(msg)
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

    Raises:
        TypeError: If template is not a string.
    """
    if not isinstance(template, str):
        msg = "Template entropy can only be calculated for a template string"
        raise TypeError(msg)

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


def estimate_profile_definition_entropy(profile_def: dict[str, Any]) -> float:
    """Estimates the entropy of a profile definition.

    Args:
        profile_def: Profile definition dictionary.

    Returns:
        Entropy in bits.

    Raises:
        ValueError: If profile definition is invalid.
    """
    if not isinstance(profile_def, dict) or "files" not in profile_def:
        raise ValueError("Profile definition must be a dict with files")

    files = resolve_profile_files(profile_def["files"])
    if not isinstance(files, dict) or not files:
        raise ValueError('Profile object must contain "files" with at least one entry')

    language = normalize_language(profile_def.get("language"))
    order = normalize_order(profile_def.get("order"))
    fields_spec = profile_def.get("fields", "all")

    entropies: dict[str, float] = {}
    for key, source in files.items():
        if not isinstance(source, str):
            raise ValueError("file references must be string list tokens or paths")
        values = list_from_name(source, language=language)
        if values is None:
            raise ValueError(
                f"Unknown list token/path: '{source}' in profile files"
            )
        n = len(values) if hasattr(values, "__len__") else 1
        entropies[key] = math.log2(n) if n > 0 else 0.0

    selected_keys = select_fields(list(files.keys()), fields_spec, order)
    entropy = sum(entropies[key] for key in selected_keys)

    if isinstance(fields_spec, int):
        total = len(files)
        k = min(fields_spec, total)
        if 0 < k < total:
            entropy += math.log2(math.comb(total, k))

    return entropy


def classify_entropy(entropy_bits: float) -> str:
    """Classifies entropy level.

    Args:
        entropy_bits: Entropy in bits.

    Returns:
        Classification string.
    """
    if entropy_bits < 28:
        return "very low"
    if entropy_bits < 40:
        return "low"
    if entropy_bits < 60:
        return "medium"
    if entropy_bits < 80:
        return "high"
    return "very high"


def main() -> None:
    """Main entry point for the passphrase generator."""
    parser = argparse.ArgumentParser(
        description="Generate passphrases using profiles.json patterns."
    )
    parser.add_argument(
        "profile",
        nargs="?",
        help="Profile name defined in profiles.json",
    )
    parser.add_argument(
        "--profile", "-p",
        dest="profile",
        help="Profile name defined in profiles.json",
    )
    parser.add_argument(
        "--count", "-n", type=int, default=1, help="How many passphrases to generate"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate profile, then exit without generating",
    )

    if len(sys.argv) == 1:
        print("=== xSpace Passphrase Generator ===")
        print("Run from PowerShell/cmd with:")
        print("  python generate_passphrase.py xspace --count 1")
        print("")
        print(
            "Usage: python generate_passphrase.py PROFILE [--count N] [--validate]"
        )
        print("Example: python generate_passphrase.py xspace --count 2")
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    if args.profile is None and not args.validate:
        parser.error("the following arguments are required: profile")

    profiles = {k.lower(): v for k, v in load_profiles(PROFILE_FILE).items()}
    profile_name = args.profile.lower()
    if profile_name not in profiles:
        raise SystemExit(f'Error: profile "{args.profile}" not found in {PROFILE_FILE}')
    profile_def = profiles[profile_name]

    if args.validate:
        try:
            rendered = render_profile_definition(profile_def)
            print("Validation successful:", rendered)
            return
        except Exception as ex:
            raise SystemExit(f"Validation failed: {ex}")

    entropy_bits = estimate_profile_definition_entropy(profile_def)
    entropy_label = classify_entropy(entropy_bits)
    print(
        f"Cognitive Passphrases Generator - Actual Entropy level [{entropy_bits:.2f}] ({entropy_label})"
    )

    for _ in range(args.count):
        print(render_profile_definition(profile_def))


if __name__ == "__main__":
    main()
