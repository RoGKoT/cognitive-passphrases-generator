from pathlib import Path
from typing import Any

from generate_passphrase import (
    load_profiles,
    list_from_name,
    normalize_language,
    normalize_marked_syntax,
    normalize_output,
    normalize_order,
    normalize_separators,
    normalize_terminal_punctuation,
    resolve_profile_files,
    select_fields,
)


def validate_profile_definition(profile_def: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(profile_def, dict):
        raise ValueError("Profile definition must be an object")

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

    if not isinstance(fields_spec, (str, int, list)):
        raise ValueError("fields must be 'all', a positive integer, or a list")

    select_fields(list(files.keys()), fields_spec, order)

    for source in files.values():
        if not isinstance(source, str):
            raise ValueError("file references must be string list tokens or paths")
        if list_from_name(source, language=language) is None:
            raise ValueError(f"Unknown list token/path: '{source}'")

    return {
        "files": files,
        "separators": separators,
        "language": language,
        "order": order,
        "fields": fields_spec,
        "output": output_mode,
        "terminal-punctuation": terminal_punctuation,
        "marked-syntax": marked_syntax_styles,
    }


def validate_profiles_file(path: Path) -> dict[str, dict[str, Any]]:
    profiles = load_profiles(path)
    if not isinstance(profiles, dict):
        raise ValueError("Profiles file must contain a JSON object of profiles")

    validated: dict[str, dict[str, Any]] = {}
    for profile_name, profile_def in profiles.items():
        validated[profile_name] = validate_profile_definition(profile_def)
    return validated
