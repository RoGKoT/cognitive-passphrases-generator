import json
import math
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import generate_passphrase
import pytest
from hypothesis import given, strategies as st

from generate_passphrase import (
    build_delimiter_values,
    build_generation_context,
    build_prefix_value,
    build_separator_values,
    build_terminal_punctuation,
    build_variation_context_from_saved_selection,
    build_separator_candidates,
    delimiter_file_name,
    format_delimiter_value,
    load_delimiter_values,
    estimate_expression_entropy,
    normalize_separators,
    estimate_parts_entropy,
    estimate_prefix_entropy,
    estimate_profile_definition_entropy,
    estimate_template_entropy,
    format_generation_details,
    list_from_name,
    load_profiles,
    render_profile_definition,
    select_supplemental_value,
    __version__,
    main,
)
from profiles import (
    collect_profiles_validation_results,
    validate_profile_definition,
    validate_profiles_file,
)

EXPECTED_DETAIL_MODE_COUNT = 2


def test_estimate_expression_entropy_for_known_list_tokens():
    # Data-driven: relies on existing timestamp JSON lists in catalog/common/timestamps
    past_entropy = math.log2(len(list_from_name("common/timestamps/past.json")))
    present_entropy = math.log2(len(list_from_name("common/timestamps/present.json")))
    future_entropy = math.log2(len(list_from_name("common/timestamps/future.json")))

    expr = "common/timestamps/past.json-common/timestamps/present.json@common/timestamps/future.json"
    estimated = estimate_expression_entropy(expr)

    assert math.isclose(
        estimated,
        past_entropy + present_entropy + future_entropy,
        rel_tol=1e-9,
    )


def test_estimate_parts_entropy_handles_separators_and_text():
    data = [
        "common/timestamps/past.json",
        "-",
        "common/timestamps/present.json",
        "@",
        "literal",
        "common/timestamps/future.json",
    ]
    # 'literal' is not a list and should contribute 0
    expected = (
        math.log2(len(list_from_name("common/timestamps/past.json")))
        + math.log2(len(list_from_name("common/timestamps/present.json")))
        + math.log2(len(list_from_name("common/timestamps/future.json")))
    )
    assert math.isclose(estimate_parts_entropy(data), expected, rel_tol=1e-9)


def test_estimate_template_entropy_looks_up_placeholders():
    tmpl = "{common/timestamps/past.json}-{common/timestamps/present.json}@{common/timestamps/future.json}"
    expected = (
        math.log2(len(list_from_name("common/timestamps/past.json")))
        + math.log2(len(list_from_name("common/timestamps/present.json")))
        + math.log2(len(list_from_name("common/timestamps/future.json")))
    )
    assert math.isclose(estimate_template_entropy(tmpl), expected, rel_tol=1e-9)


def test_estimate_profile_definition_entropy_with_profile_object():
    profile = {
        "files": {
            "past": "common/timestamps/past.json",
            "present": "common/timestamps/present.json",
            "future": "common/timestamps/future.json",
        },
        "separators": ["-", "@"],
    }
    expected = (
        math.log2(len(list_from_name("common/timestamps/past.json")))
        + math.log2(len(list_from_name("common/timestamps/present.json")))
        + math.log2(len(list_from_name("common/timestamps/future.json")))
    )
    assert estimate_profile_definition_entropy(profile) > expected


def test_estimate_profile_definition_entropy_includes_separator_choices():
    profile = {
        "files": {
            "past": "common/timestamps/past.json",
            "present": "common/timestamps/present.json",
            "future": "common/timestamps/future.json",
        },
        "separators": ["-", "@"],
    }
    entropy_with_choices = estimate_profile_definition_entropy(profile)
    entropy_single = estimate_profile_definition_entropy(
        {**profile, "separators": ["-"]},
    )
    assert entropy_with_choices > entropy_single


def test_estimate_profile_definition_entropy_includes_random_order():
    profile = {
        "files": {
            "past": "common/timestamps/past.json",
            "present": "common/timestamps/present.json",
            "future": "common/timestamps/future.json",
        },
        "separators": ["-", "@"],
    }
    normal_entropy = estimate_profile_definition_entropy(profile, order="normal")
    random_entropy = estimate_profile_definition_entropy(profile, order="random")
    assert random_entropy > normal_entropy


def test_estimate_profile_definition_entropy_includes_delimiters_fallback_to_separators():
    profile = {
        "files": {
            "past": "common/timestamps/past.json",
            "present": "common/timestamps/present.json",
        },
        "separators": {
            "enabled": True,
            "odds": 100,
            "files": {"separators": "common/separators.json"},
            "values": [],
        },
        "delimiters": {
            "enabled": True,
            "odds": 100,
            "fallback": "separators",
            "files": {"delimiters": "common/delimiters/*"},
            "values": [],
        },
    }
    entropy_with_fallback = estimate_profile_definition_entropy(profile)
    entropy_without_fallback = estimate_profile_definition_entropy(
        {**profile, "delimiters": {"enabled": False}, "separators": profile["separators"]},
    )
    assert entropy_with_fallback >= entropy_without_fallback


def test_estimate_profile_definition_entropy_includes_optional_terminal_punctuation():
    profile = {
        "files": {
            "past": "common/timestamps/past.json",
            "present": "common/timestamps/present.json",
        },
        "separators": ["-"],
        "terminal-punctuation": {
            "enabled": True,
            "odds": 50,
            "files": {"terminal-punctuation": "common/terminal-punctuations.json"},
            "values": [],
        },
    }
    punctuation_values = list_from_name("common/terminal-punctuations.json")
    expected = estimate_profile_definition_entropy(
        {"files": profile["files"], "separators": profile["separators"]},
    ) + math.log2(len(punctuation_values) + 1)
    assert math.isclose(estimate_profile_definition_entropy(profile), expected, rel_tol=1e-9)


def test_estimate_prefix_entropy_ignores_disabled_prefix():
    profile = {
        "files": {
            "past": "common/timestamps/past.json",
            "present": "common/timestamps/present.json",
        },
        "separators": ["-"],
        "prefix": {
            "enabled": False,
            "odds": 100,
            "files": {"titles": "common/prefixes/subjects/titles.json"},
            "values": [],
        },
    }
    assert estimate_profile_definition_entropy(profile) == estimate_profile_definition_entropy(
        {"files": profile["files"], "separators": ["-"]},
    )


def test_estimate_prefix_entropy_includes_legacy_prefixes():
    profile = {
        "files": {
            "past": "common/timestamps/past.json",
            "present": "common/timestamps/present.json",
        },
        "separators": ["-"],
        "prefixes": "common/prefixes/subjects/titles.json",
    }
    expected = math.log2(len(list_from_name("common/prefixes/subjects/titles.json")))
    assert math.isclose(estimate_prefix_entropy(profile), expected, rel_tol=1e-9)


def test_estimate_profile_definition_entropy_includes_space_in_delimiters_fallback(monkeypatch):
    original_load_json_file = generate_passphrase.load_json_file

    def fake_load_json_file(path):
        if path.name == "separators.json" and str(path).replace("\\", "/").endswith("common/separators.json"):
            return ["-", "@"]
        return original_load_json_file(path)

    monkeypatch.setattr(generate_passphrase, "load_json_file", fake_load_json_file)
    monkeypatch.setattr(generate_passphrase, "load_delimiter_values", lambda path: [])

    profile = {
        "files": {
            "subject:actor": "movies/peoples/actors.json",
            "subject:character": "movies/peoples/characters.json",
        },
        "separators": {
            "enabled": False,
            "odds": 100,
            "files": {"separators": "common/separators.json"},
            "values": [],
        },
        "delimiters": {
            "enabled": True,
            "odds": 0,
            "fallback": "separators",
            "files": {},
            "values": ["and"],
        },
        "space": {
            "enabled": True,
            "odds": 100,
            "files": {},
            "values": [" "],
        },
    }
    entropy_with_space = estimate_profile_definition_entropy(profile)

    profile_without_space = {
        **profile,
        "space": {
            "enabled": False,
            "odds": 100,
            "files": {},
            "values": [" "],
        },
    }
    entropy_without_space = estimate_profile_definition_entropy(profile_without_space)

    assert entropy_with_space > entropy_without_space


def test_render_profile_definition_produces_string():
    profile_def = {
        "files": {
            "past": "common/timestamps/past.json",
            "present": "common/timestamps/present.json",
            "future": "common/timestamps/future.json",
        },
        "separators": ["-", "@"],
    }
    rendered = render_profile_definition(profile_def)
    assert isinstance(rendered, str)
    assert "-" in rendered
    assert "@" in rendered


def test_render_profile_definition_preserves_profile_key_order():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "characters": "movies/peoples/characters.json",
            "heroes": "movies/peoples/heroes.json",
            "locations": "movies/titles-as/locations.json",
            "actions": "movies/titles-as/actions.json",
            "timestamps": "movies/titles-as/timestamps.json",
        },
        "separators": ["@"],
    }
    rendered = render_profile_definition(profile_def)
    parts = rendered.split("@")
    assert parts[0] in list_from_name("movies/peoples/actors.json")
    assert parts[1] in list_from_name("movies/peoples/characters.json")
    assert parts[2] in list_from_name("movies/peoples/heroes.json")
    assert parts[3] in list_from_name("movies/titles-as/locations.json")
    assert parts[4] in list_from_name("movies/titles-as/actions.json")
    assert parts[5] in list_from_name("movies/titles-as/timestamps.json")


def test_render_profile_definition_preserves_separator_sequence_in_random_order():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "characters": "movies/peoples/characters.json",
            "heroes": "movies/peoples/heroes.json",
        },
        "separators": ["@", "#"],
    }
    context = build_generation_context(profile_def, order="random")
    assert context["order"] == "random"
    assert context["separator_values"] == ["@", "#"]
    assert context["separator_entropy"] > 0
    assert context["actual_entropy"] >= context["base_entropy"]


def test_format_generation_details_shows_order_and_separators():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors/*",
            "characters": "movies/peoples/characters/*",
            "heroes": "movies/peoples/heroes/*",
        },
        "separators": ["-", "@"],
    }
    context = build_generation_context(profile_def)
    details = format_generation_details(context)
    assert "  order: normal" in details
    assert "  separators: ['-', '@']" in details
    assert "normal" in details


def test_format_generation_details_uses_random_label():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "characters": "movies/peoples/characters.json",
        },
        "separators": ["-", "@"],
    }
    context = build_generation_context(profile_def, order="random")
    details = format_generation_details(context)
    assert "random" in details


def test_format_generation_details_shows_all_output_modes():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "characters": "movies/peoples/characters.json",
        },
        "separators": ["-", "@"],
    }
    context = build_generation_context(profile_def)
    details = format_generation_details(context)
    assert "normal" in details
    assert "random" in details
    assert "Entropy level" in details


def test_format_generation_details_uses_dynamic_column_widths(monkeypatch):
    context = {
        "profile_def": {"separators": ["-"]},
        "selected_keys": ["short", "very_long_field_name_type"],
        "values_by_key": {
            "short": "A",
            "very_long_field_name_type": "very_long_value_example",
        },
        "separator_values": ["-", "@"],
        "order": "normal",
        "base_entropy": 1.0,
        "order_entropy": 0.2,
        "separator_entropy": 0.3,
        "actual_entropy": 1.5,
        "strict_entropy": 2.0,
        "strict_render": "rendered-passphrase",
        "separators": ["-", "@"],
    }

    def fake_variation(_context_arg, _order_name):
        return {"actual_entropy": 1.5, "strict_render": "rendered-passphrase"}

    monkeypatch.setattr(
        generate_passphrase,
        "build_variation_context_from_saved_selection",
        fake_variation,
    )

    details = format_generation_details(context)
    lines = details.splitlines()
    table_header_index = next(
        i
        for i, line in enumerate(lines)
        if line.startswith("  Field") and "Separator" in line
    )
    pipe_positions = [i for i, ch in enumerate(lines[table_header_index]) if ch == "|"]

    for row_line in lines[table_header_index + 2 : table_header_index + 2 + len(context["selected_keys"])]:
        assert [i for i, ch in enumerate(row_line) if ch == "|"] == pipe_positions

    assert "very_long_field_name_type" in details
    assert "very_long_value_example" in details


@patch("generate_passphrase.random_generator.shuffle")
@patch("generate_passphrase.random_generator.choice")
def test_format_generation_details_uses_same_generation_for_all_modes(
    mock_choice,
    mock_shuffle,
):
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "characters": "movies/peoples/characters.json",
            "heroes": "movies/peoples/heroes.json",
        },
        "separators": ["-", "@"],
    }

    mock_choice.side_effect = ["A", "B", "C", "-", "-"]

    def shuffle_side_effect(items):
        items[:] = [items[1], items[2], items[0]]

    mock_shuffle.side_effect = shuffle_side_effect

    context = build_generation_context(profile_def)
    details = format_generation_details(context)
    rows = [
        line
        for line in details.splitlines()
        if line.strip().startswith(("normal", "random"))
    ]
    assert len(rows) == EXPECTED_DETAIL_MODE_COUNT

    for row in rows:
        passphrase = row.split("|")[-1].strip()
        assert set(re.findall(r"[A-C]", passphrase)) == {"A", "B", "C"}


def test_render_profile_definition_with_file_object_sets_separators():
    profile_def = {
        "files": {
            "past": "common/timestamps/past.json",
            "present": "common/timestamps/present.json",
            "future": "common/timestamps/future.json",
        },
        "separators": {
            "enabled": True,
            "odds": 100,
            "files": {"separators": "common/separators.json"},
            "values": [],
        },
    }
    rendered = render_profile_definition(profile_def)
    assert isinstance(rendered, str)
    assert "|" not in rendered
    assert ";" not in rendered


def test_render_profile_definition_with_sources_json_reference():
    profile_def = {
        "files": "sources.json#movies",
        "separators": {
            "enabled": True,
            "odds": 100,
            "files": {"separators": "common/separators.json"},
            "values": [],
        },
    }
    rendered = render_profile_definition(profile_def)
    assert isinstance(rendered, str)
    assert len(rendered) > 0


def test_render_profile_definition_with_separators_all():
    profile_def = {
        "files": "sources.json#movies",
        "separators": {
            "enabled": True,
            "odds": 100,
            "files": {"separators": "common/separators.json"},
            "values": [],
        },
    }
    rendered = render_profile_definition(profile_def)
    assert isinstance(rendered, str)
    assert len(rendered) > 0
    assert "|" not in rendered
    assert ";" not in rendered


def test_validate_profile_definition_with_sources_json_reference():
    profile_def = {
        "files": "sources.json#movies",
        "separators": {
            "enabled": True,
            "odds": 100,
            "files": {"separators": "common/separators.json"},
            "values": [],
        },
    }
    validated = validate_profile_definition(profile_def)
    assert isinstance(validated["separators"], dict)


def test_validate_profile_definition_accepts_prefix_and_terminal_punctuation_and_agents():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "titles": "movies/titles.json",
        },
        "separators": {
            "enabled": True,
            "odds": 100,
            "files": {"separators": "common/separators.json"},
            "values": [],
        },
        "prefix": {
            "enabled": True,
            "odds": 50,
            "files": {"titles": "common/prefixes/subjects/titles.json"},
            "values": [],
        },
        "terminal-punctuation": {
            "enabled": True,
            "odds": 50,
            "files": {"terminal-punctuation": "common/terminal-punctuations.json"},
            "values": [],
        },
        "agents": {"api": {"name": "example", "version": "1.0"}},
    }
    validated = validate_profile_definition(profile_def)
    assert validated["prefix"]["files"]["titles"] == profile_def["prefix"]["files"]["titles"]
    assert validated["terminal-punctuation"]["enabled"] is True
    assert validated["agents"]["api"]["name"] == "example"


def test_validate_profile_definition_accepts_space_feature_object():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "titles": "movies/titles.json",
        },
        "separators": {
            "enabled": True,
            "odds": 100,
            "files": {"separators": "common/separators.json"},
            "values": [],
        },
        "delimiters": {
            "enabled": True,
            "odds": 100,
            "fallback": "separators",
            "files": {"delimiters": "common/delimiters/*"},
            "values": [],
        },
        "space": {
            "enabled": True,
            "odds": 100,
            "files": {},
            "values": [" "],
        },
    }
    validated = validate_profile_definition(profile_def)
    assert validated["space"]["enabled"] is True
    assert validated["space"]["values"] == [" "]


def test_validate_profile_definition_accepts_space_feature_list_shorthand():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "titles": "movies/titles.json",
        },
        "separators": {
            "enabled": True,
            "odds": 100,
            "files": {"separators": "common/separators.json"},
            "values": [],
        },
        "delimiters": {
            "enabled": True,
            "odds": 100,
            "fallback": "separators",
            "files": {"delimiters": "common/delimiters/*"},
            "values": [],
        },
        "space": [" "],
    }
    validated = validate_profile_definition(profile_def)
    assert validated["space"]["enabled"] is True
    assert validated["space"]["values"] == [" "]


def test_validate_profile_definition_accepts_active_space_with_delimiters_values_only():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "titles": "movies/titles.json",
        },
        "separators": {
            "enabled": True,
            "odds": 100,
            "files": {},
            "values": [","],
        },
        "delimiters": {
            "enabled": True,
            "odds": 100,
            "files": {},
            "values": [",", " "],
        },
        "space": {
            "enabled": True,
            "odds": 100,
            "files": {},
            "values": [" "],
        },
    }
    validated = validate_profile_definition(profile_def)
    assert validated["space"]["enabled"] is True
    assert validated["delimiters"]["values"] == [",", " "]


def test_validate_profile_definition_accepts_active_space_with_delimiters_fallback_and_separators_files():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "titles": "movies/titles.json",
        },
        "separators": {
            "enabled": True,
            "odds": 100,
            "files": {"separators": "common/separators.json"},
            "values": [],
        },
        "delimiters": {
            "enabled": True,
            "odds": 100,
            "fallback": "separators",
            "files": {"delimiters": "common/delimiters/*"},
            "values": [],
        },
        "space": {
            "enabled": True,
            "odds": 100,
            "files": {},
            "values": [" "],
        },
    }
    validated = validate_profile_definition(profile_def)
    assert validated["space"]["enabled"] is True
    assert validated["delimiters"]["fallback"] == "separators"


def test_validate_profile_definition_accepts_active_space_with_separators_files_and_values():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "titles": "movies/titles.json",
        },
        "separators": {
            "enabled": True,
            "odds": 100,
            "files": {"separators": "common/separators.json"},
            "values": [",", "@"],
        },
        "space": {
            "enabled": True,
            "odds": 100,
            "files": {},
            "values": [" "],
        },
    }
    validated = validate_profile_definition(profile_def)
    assert validated["space"]["enabled"] is True
    assert validated["separators"]["values"] == [",", "@"]


def test_validate_profile_definition_accepts_active_space_with_delimiters_files_only():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "titles": "movies/titles.json",
        },
        "separators": {
            "enabled": True,
            "odds": 100,
            "files": {},
            "values": [","],
        },
        "delimiters": {
            "enabled": True,
            "odds": 100,
            "files": {"delimiters": "common/delimiters/*"},
            "values": [],
        },
        "space": {
            "enabled": True,
            "odds": 100,
            "files": {},
            "values": [" "],
        },
    }
    validated = validate_profile_definition(profile_def)
    assert validated["space"]["enabled"] is True
    assert validated["delimiters"]["files"]


def test_validate_profile_definition_accepts_active_space_with_delimiters_values_only():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "titles": "movies/titles.json",
        },
        "separators": {
            "enabled": True,
            "odds": 100,
            "files": {},
            "values": [","],
        },
        "delimiters": {
            "enabled": True,
            "odds": 100,
            "files": {},
            "values": [",", " "],
        },
        "space": {
            "enabled": True,
            "odds": 100,
            "files": {},
            "values": [" "],
        },
    }
    validated = validate_profile_definition(profile_def)
    assert validated["space"]["enabled"] is True
    assert validated["delimiters"]["values"] == [",", " "]


def test_validate_profile_definition_rejects_active_space_with_separators_values_only():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "titles": "movies/titles.json",
        },
        "separators": {
            "enabled": True,
            "odds": 100,
            "files": {},
            "values": ["-"],
        },
        "space": {
            "enabled": True,
            "odds": 100,
            "files": {},
            "values": [" "],
        },
    }
    with pytest.raises(
        ValueError,
        match="Active space feature requires separators.files or enabled delimiters with values or files",
    ):
        validate_profile_definition(profile_def)


def test_validate_profile_definition_accepts_delimiters_with_fallback():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "titles": "movies/titles.json",
        },
        "separators": {
            "enabled": True,
            "odds": 100,
            "files": {"separators": "common/separators.json"},
            "values": [],
        },
        "delimiters": {
            "enabled": True,
            "odds": 100,
            "fallback": "separators",
            "files": {"delimiters": "common/delimiters/*"},
            "values": [],
        },
    }
    validated = validate_profile_definition(profile_def)
    assert validated["delimiters"]["fallback"] == "separators"


def test_validate_profile_definition_rejects_invalid_delimiters_fallback():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "titles": "movies/titles.json",
        },
        "separators": {
            "enabled": True,
            "odds": 100,
            "files": {"separators": "common/separators.json"},
            "values": [],
        },
        "delimiters": {
            "enabled": True,
            "odds": 100,
            "fallback": "invalid",
            "files": {"delimiters": "common/delimiters/*"},
            "values": [],
        },
    }
    with pytest.raises(ValueError, match="delimiters.fallback must be 'separators'"):
        validate_profile_definition(profile_def)


def test_validate_profile_definition_rejects_unsupported_keys():
    profile_def = {"files": "sources.json#movies", "output": "strict"}
    with pytest.raises(ValueError, match="Unsupported profile keys"):
        validate_profile_definition(profile_def)


def test_build_generation_context_with_delimiters_and_typed_fields():
    profile_def = {
        "files": {
            "subject:hero": "movies/peoples/heroes.json",
            "complement:location": "movies/titles.json",
        },
        "separators": {
            "enabled": False,
            "odds": 100,
            "files": {},
            "values": [],
        },
        "delimiters": {
            "enabled": True,
            "odds": 100,
            "fallback": "separators",
            "files": {"delimiters": "common/delimiters/*"},
            "values": [],
        },
    }

    with patch("generate_passphrase.random_generator.choice") as mock_choice:
        mock_choice.side_effect = [
            "HeroValue",
            "LocationValue",
            "at",
        ]
        context = build_generation_context(profile_def)

    assert context["separator_values"] == [" at "]
    assert context["rendered"] == "HeroValue at LocationValue"


def test_build_generation_context_falls_back_to_separators_when_delimiters_do_not_trigger():
    profile_def = {
        "files": {
            "subject:actor": "movies/peoples/actors.json",
            "subject:character": "movies/peoples/characters.json",
        },
        "separators": {
            "enabled": True,
            "odds": 100,
            "files": {},
            "values": [","],
        },
        "delimiters": {
            "enabled": True,
            "odds": 0,
            "fallback": "separators",
            "files": {"delimiters": "common/delimiters/*"},
            "values": [],
        },
    }

    with patch("generate_passphrase.random_generator.randrange", return_value=0), patch(
        "generate_passphrase.random_generator.choice",
    ) as mock_choice:
        mock_choice.side_effect = ["ActorValue", "CharacterValue", ","]
        context = build_generation_context(profile_def)

    assert context["separator_values"] == [","]
    assert context["rendered"] == "ActorValue,CharacterValue"
    assert mock_choice.call_count == 3


def test_build_generation_context_falls_back_to_separators_when_delimiters_do_not_trigger_and_separators_disabled():
    profile_def = {
        "files": {
            "subject:actor": "movies/peoples/actors.json",
            "subject:character": "movies/peoples/characters.json",
        },
        "separators": {
            "enabled": False,
            "odds": 100,
            "files": {"separators": "common/separators.json"},
            "values": [],
        },
        "delimiters": {
            "enabled": True,
            "odds": 0,
            "fallback": "separators",
            "files": {"delimiters": "common/delimiters/*"},
            "values": [],
        },
    }

    with patch("generate_passphrase.random_generator.randrange", return_value=0), patch(
        "generate_passphrase.random_generator.choice",
    ) as mock_choice:
        mock_choice.side_effect = ["ActorValue", "CharacterValue", ","]
        context = build_generation_context(profile_def)

    assert context["separator_values"] == [","]
    assert context["rendered"] == "ActorValue,CharacterValue"
    assert mock_choice.call_count == 3


def test_build_generation_context_applies_prefix_on_odds():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "titles": "movies/titles.json",
        },
        "separators": ["-"],
        "prefixes": "common/prefixes/subjects/titles.json",
        "odds": {"prefixes": 100},
    }

    with patch("generate_passphrase.random_generator.randrange", return_value=0), patch(
        "generate_passphrase.random_generator.choice",
    ) as mock_choice:
        mock_choice.side_effect = ["ActorValue", "TitleValue", "Dr."]
        context = build_generation_context(profile_def)

    assert context["prefix"] == "Dr."
    assert context["rendered"].startswith("Dr. ")


def test_build_generation_context_appends_terminal_punctuation_on_odds():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "titles": "movies/titles.json",
        },
        "separators": ["-"],
        "terminal-punctuation": {
            "enabled": True,
            "odds": 100,
            "files": {
                "terminal-punctuation": "common/terminal-punctuations.json",
            },
            "values": [],
        },
    }

    with patch("generate_passphrase.random_generator.randrange", return_value=0), patch(
        "generate_passphrase.random_generator.choice",
    ) as mock_choice:
        mock_choice.side_effect = ["ActorValue", "TitleValue", "?!"]
        context = build_generation_context(profile_def)

    assert context["terminal_punctuation"] == "?!"
    assert context["rendered"].endswith("?!")


def test_build_generation_context_does_not_append_terminal_punctuation_when_disabled():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "titles": "movies/titles.json",
        },
        "separators": ["-"],
        "terminal-punctuation": {
            "enabled": False,
            "odds": 100,
            "files": {
                "terminal-punctuation": "common/terminal-punctuations.json",
            },
            "values": [],
        },
    }

    with patch("generate_passphrase.random_generator.randrange", return_value=0), patch(
        "generate_passphrase.random_generator.choice",
    ) as mock_choice:
        mock_choice.side_effect = ["ActorValue", "TitleValue"]
        context = build_generation_context(profile_def)

    assert context["terminal_punctuation"] == ""
    assert not context["rendered"].endswith("?")
    assert not context["rendered"].endswith("!")


def test_build_generation_context_appends_terminal_punctuation_when_enabled_boolean_true():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "titles": "movies/titles.json",
        },
        "separators": ["-"],
        "terminal-punctuation": {
            "enabled": True,
            "odds": 100,
            "files": {
                "terminal-punctuation": "common/terminal-punctuations.json",
            },
            "values": [],
        },
    }

    with patch("generate_passphrase.random_generator.randrange", return_value=0), patch(
        "generate_passphrase.random_generator.choice",
    ) as mock_choice:
        mock_choice.side_effect = ["ActorValue", "TitleValue", "?!"]
        context = build_generation_context(profile_def)

    assert context["terminal_punctuation"] == "?!"
    assert context["rendered"].endswith("?!")


def test_select_supplemental_value_respects_space_odds():
    values = [" ", "at", "in"]
    with patch("generate_passphrase.random_generator.randrange", return_value=0), patch(
        "generate_passphrase.random_generator.choice",
    ) as mock_choice:
        mock_choice.side_effect = [" "]
        result = select_supplemental_value(values, {"space": 100})

    assert result == " "


def test_build_delimiter_values_formats_common_tokens():
    with patch("generate_passphrase.load_delimiter_values") as mock_load, patch(
        "generate_passphrase.random_generator.choice",
    ) as mock_choice:
        mock_load.return_value = [",", "and", "@"]
        mock_choice.side_effect = [",", "and"]
        values = build_delimiter_values(["subject:actor", "subject:character", "verb:action"], {"space": 0})

    assert values == [", ", " and "]
    mock_load.assert_any_call("subject-subject.json")
    mock_load.assert_any_call("subject-action.json")


def test_build_separator_values_preserves_explicit_separators():
    values = build_separator_values([",", "and"], 2, "normal")
    assert values == [",", "and"]


def test_build_separator_values_preserves_all_separators():
    separators = normalize_separators([",", "and"])
    values = build_separator_values(separators, 2, "normal")
    assert values == [",", "and"]


def test_normalize_separators_requires_list():
    with pytest.raises(TypeError, match="separators must be a list"):
        normalize_separators("all")


def test_build_separator_values_randomizes_candidate_separators():
    with patch("generate_passphrase.random_generator.choice") as mock_choice:
        mock_choice.side_effect = ["@", "#"]
        values = build_separator_values(["@", "#"], 2, "normal", randomize=True)

    assert values == ["@", "#"]


def test_render_profile_definition_preserves_explicit_separators():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "titles": "movies/titles.json",
        },
        "separators": [","],
    }
    rendered = render_profile_definition(profile_def)
    assert "," in rendered
    assert ", " not in rendered


def test_build_delimiter_values_uses_subject_subject_file():
    with patch("generate_passphrase.load_delimiter_values") as mock_load:
        mock_load.return_value = [" ", "and"]
        values = build_delimiter_values(["subject:actor", "subject:character"], {"space": 100})

    assert values == [" "]
    mock_load.assert_called_once_with("subject-subject.json")


def test_build_prefix_value_obeys_odds():
    with patch("generate_passphrase.random_generator.randrange", return_value=0), patch(
        "generate_passphrase.random_generator.choice",
    ) as mock_choice:
        mock_choice.return_value = "Dr."
        prefix = build_prefix_value(
            {"prefixes": "common/prefixes/subjects/titles.json"},
            {"prefixes": 100},
        )

    assert prefix == "Dr."


def test_build_terminal_punctuation_does_not_end_with_space():
    profile_def = {
        "terminal-punctuation": "enabled",
        "odds": {"terminal-punctuation": 100},
    }
    with patch("generate_passphrase.random_generator.randrange", return_value=0), patch(
        "generate_passphrase.random_generator.choice",
    ) as mock_choice:
        mock_choice.return_value = "?!"
        punctuation = build_terminal_punctuation(profile_def, {"terminal-punctuation": 100})

    assert punctuation == "?!"


def test_validate_profile_definition_rejects_empty_string_in_main_list_source():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
        },
        "separators": {
            "enabled": True,
            "odds": 100,
            "files": {"separators": "common/separators.json"},
            "values": [],
        },
    }

    with patch("profiles.validation.list_from_name", return_value=["", "Actor"]):
        with pytest.raises(ValueError, match="contains empty-string entries"):
            validate_profile_definition(profile_def)


def test_validate_profile_definition_rejects_empty_string_in_terminal_punctuation_source():
    profile_def = {
        "files": {
            "punctuation": "common/terminal-punctuations.json",
        },
        "separators": {
            "enabled": True,
            "odds": 100,
            "files": {"separators": "common/separators.json"},
            "values": [],
        },
        "terminal-punctuation": {
            "enabled": True,
            "odds": 100,
            "files": {"terminal-punctuation": "common/terminal-punctuations.json"},
            "values": [],
        },
    }

    def list_from_name_side_effect(source):
        if source == "common/terminal-punctuations.json":
            return ["", "?!"]
        return ["Actor"]

    with patch("profiles.validation.list_from_name", side_effect=list_from_name_side_effect):
        with pytest.raises(ValueError, match="terminal punctuation"):
            validate_profile_definition(profile_def)


def test_validate_profile_definition_rejects_wrong_terminal_punctuation_path():
    profile_def = {
        "files": {
            "punctuation": "common/terminal-punctuation.json",
        },
        "separators": {
            "enabled": True,
            "odds": 100,
            "files": {"separators": "common/separators.json"},
            "values": [],
        },
        "terminal-punctuation": {
            "enabled": True,
            "odds": 100,
            "files": {"terminal-punctuation": "common/terminal-punctuation.json"},
            "values": [],
        },
    }

    with pytest.raises(ValueError, match="Unknown list token/path"):
        validate_profile_definition(profile_def)


def test_validate_profile_definition_rejects_missing_list_file():
    profile_def = {
        "files": {
            "subject": "common/this-file-does-not-exist.json",
        },
        "separators": {
            "enabled": True,
            "odds": 100,
            "files": {},
            "values": [" "],
        },
    }

    with pytest.raises(ValueError, match="Unknown list token/path"):
        validate_profile_definition(profile_def)


def test_validate_profiles_file():
    validated = validate_profiles_file(Path("profiles") / "profiles.json")
    assert "example" in validated
    assert "movies" in validated


def test_version_comes_from_pyproject():
    assert __version__ == "0.9.0"


def _allowed_cli_separator_values(profile_def: dict[str, object], keys: list[str]) -> set[str]:
    separators = set(build_separator_candidates(profile_def, ignore_disabled_separators=True))
    delimiter_feature = profile_def.get("delimiters")
    if isinstance(delimiter_feature, dict):
        explicit_values = delimiter_feature.get("values", [])
        for value in explicit_values:
            if isinstance(value, str):
                separators.add(format_delimiter_value(value))
        for left, right in zip(keys, keys[1:]):
            try:
                typed_candidates = load_delimiter_values(delimiter_file_name(left, right))
            except FileNotFoundError:
                typed_candidates = []
            for value in typed_candidates:
                if isinstance(value, str):
                    separators.add(format_delimiter_value(value))
    return separators


def test_generate_passphrase_cli_test_profile_matches_profile_sources():
    repo_root = Path(__file__).resolve().parent
    profile_def = validate_profiles_file(repo_root / "profiles" / "profiles.json")["test"]

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "generate_passphrase.py"),
            "test",
            "--count",
            "1",
            "--details",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )

    output_lines = [line.rstrip() for line in result.stdout.splitlines()]
    field_lines = []
    for line in output_lines:
        if "|" not in line:
            continue
        left = line.split("|", 1)[0].strip()
        if not left or left in {"Field", "output", "normal", "random"}:
            continue
        if set(left) <= {"-"}:
            continue
        field_lines.append(line)

    assert field_lines, "Expected field details in CLI output"

    keys: list[str] = []
    separators: list[str] = []
    for line in field_lines:
        parts = [part.strip() for part in line.split("|")]
        assert len(parts) >= 3
        field_name = parts[0]
        field_value = parts[1]
        separator_value = parts[2].strip("'")

        keys.append(field_name)
        assert field_value in list_from_name(profile_def["files"][field_name])
        if separator_value:
            separators.append(separator_value)

    allowed_separators = _allowed_cli_separator_values(profile_def, keys)
    for separator_value in separators:
        assert separator_value in allowed_separators


def test_collect_profiles_validation_results_skips_invalid_profiles(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text(
        json.dumps(
            {
                "valid": {
                    "files": {
                        "subject:hero": "movies/peoples/heroes.json",
                    },
                    "separators": {
                        "enabled": True,
                        "odds": 100,
                        "files": {},
                        "values": [" "],
                    },
                },
                "invalid": {
                    "files": {},
                    "separators": {
                        "enabled": True,
                        "odds": 100,
                        "files": {},
                        "values": [" "],
                    },
                },
            },
        ),
        encoding="utf-8",
    )

    validated, errors = collect_profiles_validation_results(path)
    assert "valid" in validated
    assert "invalid" not in validated
    assert "invalid" in errors
    assert "files" in errors["invalid"]


def test_validate_profiles_file_aggregates_invalid_profiles(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text(
        json.dumps(
            {
                "valid": {
                    "files": {
                        "subject:hero": "movies/peoples/heroes.json",
                    },
                    "separators": {
                        "enabled": True,
                        "odds": 100,
                        "files": {},
                        "values": [" "],
                    },
                },
                "invalid": {
                    "files": {},
                    "separators": {
                        "enabled": True,
                        "odds": 100,
                        "files": {},
                        "values": [" "],
                    },
                },
            },
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Profiles file contains invalid profile definitions"):
        validate_profiles_file(path)


def test_list_from_name_supports_leading_slash():
    assert list_from_name("/common/timestamps/past.json") == list_from_name(
        "common/timestamps/past.json",
    )


def test_profile_definition_requires_files():
    with pytest.raises(
        ValueError,
        match="Profile definition must be a dict with files",
    ):
        estimate_profile_definition_entropy(
            {"pattern": "xspace/movies.action-titles.json"},
        )


def test_list_from_name_non_json_returns_none():
    assert list_from_name("xspace/movies.action-titles") is None


def test_wildcard_directory_tokens():
    result = list_from_name("common/timestamps/*")
    assert isinstance(result, list)
    assert "past" not in result  # deve être des strings spécifiques pas le token


def test_load_profiles_rejects_non_dict_json(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text('["not", "a", "dict"]', encoding="utf-8")

    with pytest.raises(
        TypeError,
        match=r"Profiles file .* did not contain a JSON object",
    ):
        load_profiles(path)


def test_load_profiles_accepts_json_comments(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text(
        '{\n'
        '  "movies": {\n'
        '    "files": {"subject:actor": "movies/peoples/actors.json"},\n'
        '    "space": { // comment\n'
        '      "enabled": true,\n'
        '      "odds": 100,\n'
        '      "files": {},\n'
        '      "values": [" "]\n'
        '    }\n'
        '  }\n'
        '}',
        encoding="utf-8",
    )
    profiles = load_profiles(path)

    assert "movies" in profiles
    assert profiles["movies"]["space"]["enabled"] is True


def test_build_variation_context_from_saved_selection_preserves_normal_order():
    profile_def = {
        "files": {
            "actors": "movies/peoples/actors.json",
            "heroes": "movies/peoples/heroes.json",
        },
        "separators": ["-"],
    }
    base_context = build_generation_context(profile_def, order="normal")
    variation_context = build_variation_context_from_saved_selection(
        base_context,
        order="normal",
    )

    assert variation_context["selected_keys"] == base_context["selected_keys"]
    assert variation_context["order"] == "normal"


# pytest discovery; run `pytest -q` now


@given(st.text())
def test_estimate_expression_entropy_non_negative(expr):
    """Test that expression entropy is always non-negative."""
    entropy = estimate_expression_entropy(expr)
    assert entropy >= 0.0


@given(st.lists(st.text()))
def test_estimate_parts_entropy_non_negative(parts):
    """Test that parts entropy is always non-negative."""
    try:
        entropy = estimate_parts_entropy(parts)
        assert entropy >= 0.0
    except ValueError:
        # Invalid parts, skip
        pass


@given(st.text())
def test_estimate_template_entropy_non_negative(template):
    """Test that template entropy is always non-negative."""
    entropy = estimate_template_entropy(template)
    assert entropy >= 0.0


def test_entropy_summary_printed_once_for_multiple_count(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        ["generate_passphrase.py", "xspace", "--count", "3"],
    )
    main()
    captured = capsys.readouterr()
    assert captured.out.count(
        "Cognitive Passphrases Generator - Actual Entropy level [",
    ) == 1
