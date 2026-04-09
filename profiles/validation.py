from pathlib import Path
from typing import Any

from generate_passphrase import (
    DATA_DIR,
    CATALOG_DIR,
    list_from_name,
    load_json_file,
    load_profiles,
    normalize_path,
    resolve_profile_files,
)


def _is_terminal_punctuation_source(source: str) -> bool:
    normalized = normalize_path(source)
    return normalized.endswith("terminal-punctuations.json")


def _find_list_source_candidates(source: str) -> list[Path]:
    stable_name = normalize_path(source)
    if not stable_name:
        return []

    if ".." in stable_name:
        raise ValueError(f"Invalid list token: {stable_name}")

    candidates: list[Path] = []
    if "*" in stable_name:
        for base_root in [DATA_DIR, CATALOG_DIR]:
            candidates.extend(sorted(base_root.glob(stable_name)))

        if stable_name.endswith("/*"):
            prefix = stable_name[:-2]
            for base_root in [DATA_DIR, CATALOG_DIR]:
                alternate = base_root / f"{prefix}.json"
                if alternate.exists() and alternate.is_file():
                    candidates.append(alternate)

        return [path for path in candidates if path.is_file()]

    if not stable_name.endswith(".json"):
        return []

    candidate_paths: list[Path] = [
        DATA_DIR / stable_name,
        DATA_DIR / "categories" / stable_name,
        CATALOG_DIR / stable_name,
        CATALOG_DIR / "categories" / stable_name,
    ]

    for candidate in candidate_paths:
        if candidate.exists() and candidate.is_file():
            candidates.append(candidate)
        alternate = candidate.with_suffix("")
        if alternate.exists() and alternate.is_file():
            candidates.append(alternate)

    return candidates


def _validate_list_source_structure(source: str) -> None:
    candidates = _find_list_source_candidates(source)
    if not candidates:
        raise ValueError(f"Unknown list token/path: '{source}'")

    for path in candidates:
        values = load_json_file(path)
        if values is None:
            raise ValueError(
                f"List source '{source}' exists at '{path}' but is not valid JSON or not a list.",
            )
        if not isinstance(values, list):
            raise ValueError(
                f"List source '{source}' exists at '{path}' but contains {type(values).__name__} instead of a JSON list.",
            )


def _validate_source_list_for_empty_string(source: str) -> None:
    values = list_from_name(source)
    if values is None:
        _validate_list_source_structure(source)
        return

    if any(value == "" for value in values):
        if _is_terminal_punctuation_source(source):
            raise ValueError(
                f"List source '{source}' contains empty-string entries. "
                "Do not use empty-string values in terminal punctuation lists. "
                "Remove the blank entries and configure terminal punctuation explicitly: "
                "'terminal-punctuation': 'enabled' and 'odds.terminal-punctuation' in the profile, "
                "and ensure 'odds.terminal-punctuation' is present in profiles/cognitive-passphrases-generator.json.",
            )
        raise ValueError(
            f"List source '{source}' contains empty-string entries. "
            "Remove the blank entries from the list file.",
        )


def _validate_feature_object(
    feature_def: Any,
    feature_name: str,
    allow_fallback: bool = False,
) -> None:
    if not isinstance(feature_def, dict):
        raise TypeError(f"{feature_name} must be an object")

    supported_keys = {"enabled", "odds", "files", "values"}
    if allow_fallback:
        supported_keys.add("fallback")

    unsupported_keys = [
        key
        for key in feature_def
        if key not in supported_keys
    ]
    if unsupported_keys:
        raise ValueError(
            f"Unsupported keys in {feature_name}: "
            + ", ".join(sorted(unsupported_keys)),
        )

    enabled = feature_def.get("enabled")
    if not isinstance(enabled, bool):
        raise TypeError(f"{feature_name}.enabled must be a boolean")

    odds = feature_def.get("odds")
    if not isinstance(odds, (int, float)):
        raise TypeError(f"{feature_name}.odds must be numeric")
    if odds < 0 or odds > 100:
        raise ValueError(f"{feature_name}.odds must be between 0 and 100")

    file_sources = feature_def.get("files", {})
    if not isinstance(file_sources, dict):
        raise TypeError(f"{feature_name}.files must be an object")
    for source in file_sources.values():
        if not isinstance(source, str):
            raise TypeError(f"{feature_name}.files values must be strings")
        _validate_source_list_for_empty_string(source)

    values = feature_def.get("values", [])
    if not isinstance(values, list):
        raise TypeError(f"{feature_name}.values must be a list")
    for value in values:
        if not isinstance(value, str):
            raise TypeError(f"{feature_name}.values must be strings")
        if value == "":
            raise ValueError(f"{feature_name}.values must not contain empty strings")

    if allow_fallback and "fallback" in feature_def:
        fallback = feature_def["fallback"]
        if not isinstance(fallback, str):
            raise TypeError("delimiters.fallback must be a string")
        if fallback != "separators":
            raise ValueError("delimiters.fallback must be 'separators'")

    if enabled and not (file_sources or values):
        raise ValueError(
            f"{feature_name} must include at least one file source or explicit value when enabled",
        )


def validate_profile_definition(profile_def: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(profile_def, dict):
        message = "Profile definition must be an object"
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

    separators = profile_def.get("separators")
    if isinstance(separators, list):
        separators = {
            "enabled": True,
            "odds": 100,
            "files": {},
            "values": separators,
        }
    if separators is None or not isinstance(separators, dict):
        raise TypeError("separators must be an object or list")
    _validate_feature_object(separators, "separators")

    prefix = profile_def.get("prefix")
    if prefix is not None:
        if not isinstance(prefix, dict):
            raise TypeError("prefix must be an object")
        _validate_feature_object(prefix, "prefix")

    delimiters = profile_def.get("delimiters")
    if delimiters is not None:
        if not isinstance(delimiters, dict):
            raise TypeError("delimiters must be an object")
        _validate_feature_object(delimiters, "delimiters", allow_fallback=True)

    terminal_punctuation = profile_def.get("terminal-punctuation")
    if terminal_punctuation is not None:
        if not isinstance(terminal_punctuation, dict):
            raise TypeError("terminal-punctuation must be an object")
        _validate_feature_object(terminal_punctuation, "terminal-punctuation")

    space = profile_def.get("space")
    if isinstance(space, list):
        space = {
            "enabled": True,
            "odds": 100,
            "files": {},
            "values": space,
        }
    if space is not None:
        if not isinstance(space, dict):
            raise TypeError("space must be an object or list")
        _validate_feature_object(space, "space")

        if space["enabled"]:
            has_valid_separators = (
                isinstance(separators, dict)
                and separators.get("enabled", False)
                and isinstance(separators.get("files", {}), dict)
                and bool(separators.get("files", {}))
            )
            has_valid_delimiters = False
            if isinstance(delimiters, dict) and delimiters.get("enabled", False):
                delimiter_files = delimiters.get("files", {})
                delimiter_values = delimiters.get("values", [])
                if isinstance(delimiter_files, dict) and delimiter_files:
                    has_valid_delimiters = True
                elif isinstance(delimiter_values, list) and delimiter_values:
                    has_valid_delimiters = True

            if not has_valid_separators and not has_valid_delimiters:
                raise ValueError(
                    "Active space feature requires separators.files or enabled delimiters with values or files. "
                    "It cannot work with separators.values alone.",
                )

    agents = profile_def.get("agents")
    if agents is not None and not isinstance(agents, dict):
        raise TypeError("agents must be an object")

    for source in files.values():
        if not isinstance(source, str):
            message = "file references must be string list tokens or paths"
            raise TypeError(message)
        _validate_source_list_for_empty_string(source)

    validated: dict[str, Any] = {
        "files": files,
        "separators": separators,
    }
    if delimiters is not None:
        validated["delimiters"] = delimiters
    if prefix is not None:
        validated["prefix"] = prefix
    if terminal_punctuation is not None:
        validated["terminal-punctuation"] = terminal_punctuation
    if space is not None:
        validated["space"] = space
    if agents is not None:
        validated["agents"] = agents
    return validated


def _validate_profiles_file_details(
    path: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    profiles = load_profiles(path)
    if not isinstance(profiles, dict):
        message = "Profiles file must contain a JSON object of profiles"
        raise TypeError(message)

    validated: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    for profile_name, profile_def in profiles.items():
        try:
            validated[profile_name] = validate_profile_definition(profile_def)
        except (TypeError, ValueError, FileNotFoundError) as ex:
            errors[profile_name] = str(ex)

    return validated, errors


def collect_profiles_validation_results(
    path: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    return _validate_profiles_file_details(path)


def validate_profiles_file(path: Path) -> dict[str, dict[str, Any]]:
    validated, errors = _validate_profiles_file_details(path)
    if errors:
        message = "Profiles file contains invalid profile definitions:\n"
        message += "\n".join(
            f"{profile_name}: {error}" for profile_name, error in sorted(errors.items())
        )
        raise ValueError(message)
    return validated
