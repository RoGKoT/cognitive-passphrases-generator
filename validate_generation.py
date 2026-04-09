#!/usr/bin/env python3
import argparse
import sys
from typing import Any

from generate_passphrase import (
    PROFILE_FILE,
    __version__,
    build_feature_candidates,
    build_generation_context,
    build_separator_candidates,
    delimiter_file_name,
    format_delimiter_value,
    format_generation_details,
    is_terminal_punctuation_enabled,
    list_from_name,
    load_delimiter_values,
    load_profiles,
    resolve_profile_files,
)
from profiles import validate_profile_definition


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate passphrase generation against a profile definition.",
    )
    parser.add_argument(
        "--profile",
        "-p",
        default="test",
        help="Profile name defined in profiles.json",
    )
    parser.add_argument(
        "--count",
        "-n",
        type=int,
        default=1,
        help="How many passphrases to generate and validate",
    )
    parser.add_argument(
        "--random",
        dest="order",
        action="store_const",
        const="random",
        default="normal",
        help="Use random field order instead of normal order",
    )
    parser.add_argument(
        "--log-process",
        action="store_true",
        help="Log each generation step and source provenance",
    )
    return parser.parse_args()


def load_requested_profile(profile_name: str) -> dict[str, Any]:
    profiles = load_profiles(PROFILE_FILE)
    if not isinstance(profiles, dict):
        raise ValueError(f"Profiles file {PROFILE_FILE} did not contain a JSON object")

    normalized_profiles = {k.lower(): v for k, v in profiles.items()}
    profile_key = profile_name.lower()
    if profile_key not in normalized_profiles:
        raise ValueError(f'Profile "{profile_name}" not found in {PROFILE_FILE}')

    profile_def = normalized_profiles[profile_key]
    validate_profile_definition(profile_def)
    ensure_profile_completeness(profile_def)
    return profile_def


def ensure_profile_completeness(profile_def: dict[str, Any]) -> None:
    files = resolve_profile_files(profile_def.get("files"))
    if not isinstance(files, dict) or not files:
        raise ValueError("Profile files must be defined and non-empty")

    for key, source in files.items():
        if not isinstance(source, str) or not source.strip():
            raise ValueError(f"Profile file source for '{key}' must be a non-empty string")


def normalize_prefix_feature(profile_def: dict[str, Any]) -> dict[str, Any]:
    prefix_feature = profile_def.get("prefix")
    if isinstance(prefix_feature, dict):
        return prefix_feature

    legacy_prefixes = profile_def.get("prefixes")
    prefix_odds = 0
    if isinstance(profile_def.get("odds"), dict):
        prefix_odds = profile_def["odds"].get("prefixes", 0)

    if isinstance(legacy_prefixes, str):
        return {
            "enabled": True,
            "odds": prefix_odds,
            "files": {"prefixes": legacy_prefixes},
            "values": [],
        }
    if isinstance(legacy_prefixes, list):
        return {
            "enabled": True,
            "odds": prefix_odds,
            "files": {},
            "values": legacy_prefixes,
        }
    return {}


def resolve_terminal_feature(profile_def: dict[str, Any]) -> dict[str, Any]:
    terminal_feature = profile_def.get("terminal-punctuation")
    if isinstance(terminal_feature, dict):
        return terminal_feature

    if is_terminal_punctuation_enabled(terminal_feature):
        terminal_odds = 0
        if isinstance(profile_def.get("odds"), dict):
            terminal_odds = profile_def["odds"].get("terminal-punctuation", 0)
        return {
            "enabled": True,
            "odds": terminal_odds,
            "files": {"terminal-punctuation": "common/terminal-punctuations.json"},
            "values": [],
        }
    return {}


def allowed_delimiter_values(profile_def: dict[str, Any], keys: list[str]) -> list[str]:
    delimiter_feature = profile_def.get("delimiters")
    if not isinstance(delimiter_feature, dict):
        return []

    explicit_values = delimiter_feature.get("values", [])
    if not isinstance(explicit_values, list):
        raise TypeError("delimiters.values must be a list")

    raw_values: list[str] = []
    for item in explicit_values:
        if not isinstance(item, str):
            raise TypeError("delimiters.values must be strings")
        raw_values.append(item)

    for left, right in zip(keys, keys[1:]):
        try:
            typed_candidates = load_delimiter_values(delimiter_file_name(left, right))
        except FileNotFoundError:
            typed_candidates = []
        for value in typed_candidates or []:
            if isinstance(value, str):
                raw_values.append(value)

    return [format_delimiter_value(value) for value in raw_values]


def validate_generated_context(context: dict[str, Any], profile_def: dict[str, Any]) -> None:
    profile_files = resolve_profile_files(profile_def.get("files"))
    if not isinstance(profile_files, dict):
        raise ValueError("Profile files must be defined and non-empty")

    for key, selected_value in context["values_by_key"].items():
        source = profile_files[key]
        if not isinstance(source, str):
            raise TypeError("file references must be string list tokens or paths")
        allowed_values = list_from_name(source)
        if allowed_values is None:
            raise ValueError(f"Unknown list token/path: '{source}'")
        if selected_value not in allowed_values:
            raise ValueError(
                f"Generated value '{selected_value}' for field '{key}' is not allowed by source '{source}'",
            )

    separator_values = context["separator_values"]
    delimiter_values = allowed_delimiter_values(profile_def, context["selected_keys"])
    separator_candidates = build_separator_candidates(profile_def, ignore_disabled_separators=True)

    for separator in separator_values:
        if separator == "":
            continue
        if separator not in separator_candidates and separator not in delimiter_values:
            raise ValueError(
                f"Generated separator '{separator}' is not allowed by profile separators or delimiters",
            )

    prefix_value = context.get("prefix", "")
    if prefix_value:
        prefix_candidates = build_feature_candidates(normalize_prefix_feature(profile_def))
        if prefix_value not in prefix_candidates:
            raise ValueError(
                f"Generated prefix '{prefix_value}' is not allowed by the profile prefix sources",
            )

    punctuation_value = context.get("terminal_punctuation", "")
    if punctuation_value:
        terminal_candidates = build_feature_candidates(resolve_terminal_feature(profile_def))
        if punctuation_value not in terminal_candidates:
            raise ValueError(
                f"Generated terminal punctuation '{punctuation_value}' is not allowed by the profile",
            )


def log_context(iteration: int, context: dict[str, Any]) -> None:
    print(f"Iteration {iteration + 1}")
    print(format_generation_details(context))
    print(context["rendered"])
    print()


def main() -> None:
    args = parse_args()
    try:
        profile_def = load_requested_profile(args.profile)
    except (ValueError, FileNotFoundError, TypeError) as ex:
        raise SystemExit(str(ex)) from ex

    print(f"Validating generation for profile '{args.profile}' from {PROFILE_FILE} (version v{__version__})")
    print(f"Iteration count: {args.count}")
    print(f"Order: {args.order}")
    print(f"Log process: {'enabled' if args.log_process else 'disabled'}")
    print()

    for iteration in range(args.count):
        context = build_generation_context(profile_def, args.order)
        try:
            validate_generated_context(context, profile_def)
        except (TypeError, ValueError) as ex:
            raise SystemExit(f"Validation failed on iteration {iteration + 1}: {ex}") from ex

        if args.log_process:
            log_context(iteration, context)
        else:
            print(context["rendered"])

    print(f"Validation succeeded for profile '{args.profile}' ({args.count} passphrase(s)).")


if __name__ == "__main__":
    main()
