from pathlib import Path
from typing import Any

from generate_passphrase import (
    list_from_name,
    load_profiles,
    normalize_separators,
    resolve_profile_files,
)


def validate_profile_definition(profile_def: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(profile_def, dict):
        message = "Profile definition must be an object"
        raise TypeError(message)

    unsupported_keys = [
        key for key in profile_def if key not in {"files", "separators"}
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

    separators = normalize_separators(profile_def.get("separators", []))

    for source in files.values():
        if not isinstance(source, str):
            message = "file references must be string list tokens or paths"
            raise TypeError(message)
        if list_from_name(source) is None:
            message = f"Unknown list token/path: '{source}'"
            raise ValueError(message)

    return {
        "files": files,
        "separators": separators,
    }


def validate_profiles_file(path: Path) -> dict[str, dict[str, Any]]:
    profiles = load_profiles(path)
    if not isinstance(profiles, dict):
        message = "Profiles file must contain a JSON object of profiles"
        raise TypeError(message)

    validated: dict[str, dict[str, Any]] = {}
    for profile_name, profile_def in profiles.items():
        validated[profile_name] = validate_profile_definition(profile_def)
    return validated
