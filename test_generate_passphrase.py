import math
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, strategies as st

from generate_passphrase import (
    build_generation_context,
    build_variation_context_from_saved_selection,
    estimate_expression_entropy,
    estimate_parts_entropy,
    estimate_profile_definition_entropy,
    estimate_template_entropy,
    format_generation_details,
    list_from_name,
    load_profiles,
    render_profile_definition,
    main,
)
from profiles import validate_profile_definition, validate_profiles_file

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
            "actions": "movies/titles-as/verbs.json",
            "timestamps": "movies/titles-as/timestamps.json",
        },
        "separators": ["-"],
    }
    rendered = render_profile_definition(profile_def)
    parts = rendered.split("-")
    assert parts[0] in list_from_name("movies/peoples/actors.json")
    assert parts[1] in list_from_name("movies/peoples/characters.json")
    assert parts[2] in list_from_name("movies/peoples/heroes.json")
    assert parts[3] in list_from_name("movies/titles-as/locations.json")
    assert parts[4] in list_from_name("movies/titles-as/verbs.json")
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
        "separators": ["-", "@"],
    }
    rendered = render_profile_definition(profile_def)
    assert isinstance(rendered, str)
    assert "-" in rendered
    assert "@" in rendered


def test_render_profile_definition_with_sources_json_reference():
    profile_def = {"files": "sources.json#movies", "separators": ["@", "-"]}
    rendered = render_profile_definition(profile_def)
    assert isinstance(rendered, str)
    assert len(rendered) > 0


def test_render_profile_definition_with_separators_all():
    profile_def = {"files": "sources.json#movies", "separators": "all"}
    rendered = render_profile_definition(profile_def)
    assert isinstance(rendered, str)
    assert len(rendered) > 0
    assert "|" not in rendered
    assert ";" not in rendered


def test_validate_profile_definition_with_sources_json_reference():
    profile_def = {"files": "sources.json#movies", "separators": ["@", "-"]}
    validated = validate_profile_definition(profile_def)
    assert isinstance(validated["separators"], list)


def test_validate_profile_definition_rejects_unsupported_keys():
    profile_def = {"files": "sources.json#movies", "output": "strict"}
    with pytest.raises(ValueError, match="Unsupported profile keys"):
        validate_profile_definition(profile_def)


def test_validate_profiles_file():
    validated = validate_profiles_file(Path("profiles") / "profiles.json")
    assert "xspace" in validated
    assert "movies" in validated


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
