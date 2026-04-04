import math
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from generate_passphrase import (
    estimate_expression_entropy,
    estimate_parts_entropy,
    estimate_template_entropy,
    estimate_profile_definition_entropy,
    list_from_name,
    render_profile_definition,
)
from profiles import validate_profile_definition, validate_profiles_file


def test_estimate_expression_entropy_for_known_list_tokens():
    # Data-driven: relies on existing timestamp JSON lists in catalog/common/timestamps
    past_entropy = math.log2(len(list_from_name('common/timestamps/past.json')))
    present_entropy = math.log2(len(list_from_name('common/timestamps/present.json')))
    future_entropy = math.log2(len(list_from_name('common/timestamps/future.json')))

    expr = 'common/timestamps/past.json-common/timestamps/present.json@common/timestamps/future.json'
    estimated = estimate_expression_entropy(expr)

    assert math.isclose(estimated, past_entropy + present_entropy + future_entropy, rel_tol=1e-9)


def test_estimate_parts_entropy_handles_separators_and_text():
    data = ['common/timestamps/past.json', '-', 'common/timestamps/present.json', '@', 'literal', 'common/timestamps/future.json']
    # 'literal' is not a list and should contribute 0
    expected = math.log2(len(list_from_name('common/timestamps/past.json'))) + math.log2(len(list_from_name('common/timestamps/present.json'))) + math.log2(len(list_from_name('common/timestamps/future.json')))
    assert math.isclose(estimate_parts_entropy(data), expected, rel_tol=1e-9)


def test_estimate_template_entropy_looks_up_placeholders():
    tmpl = '{common/timestamps/past.json}-{common/timestamps/present.json}@{common/timestamps/future.json}'
    expected = math.log2(len(list_from_name('common/timestamps/past.json'))) + math.log2(len(list_from_name('common/timestamps/present.json'))) + math.log2(len(list_from_name('common/timestamps/future.json')))
    assert math.isclose(estimate_template_entropy(tmpl), expected, rel_tol=1e-9)


def test_estimate_profile_definition_entropy_with_profile_object():
    profile = {
        'files': {
            'past': 'common/timestamps/past.json',
            'present': 'common/timestamps/present.json',
            'future': 'common/timestamps/future.json'
        },
        'separators': ['-', '@']
    }
    expected = (
        math.log2(len(list_from_name('common/timestamps/past.json'))) +
        math.log2(len(list_from_name('common/timestamps/present.json'))) +
        math.log2(len(list_from_name('common/timestamps/future.json')))
    )
    assert math.isclose(estimate_profile_definition_entropy(profile), expected, rel_tol=1e-9)


def test_render_profile_definition_produces_string():
    profile_def = {
        'files': {
            'past': 'common/timestamps/past.json',
            'present': 'common/timestamps/present.json',
            'future': 'common/timestamps/future.json'
        },
        'separators': ['-', '@']
    }
    rendered = render_profile_definition(profile_def)
    assert isinstance(rendered, str)
    assert '-' in rendered and '@' in rendered


def test_render_profile_definition_with_file_object_sets_separators():
    profile_def = {
        'files': {
            'past': 'common/timestamps/past.json',
            'present': 'common/timestamps/present.json',
            'future': 'common/timestamps/future.json'
        },
        'separators': ['-', '@']
    }
    rendered = render_profile_definition(profile_def)
    assert isinstance(rendered, str)
    assert '-' in rendered and '@' in rendered


def test_render_profile_definition_with_sources_json_reference():
    profile_def = {
        'files': 'sources.json#movies',
        'language': 'en-us',
        'fields': 3,
        'order': 'random',
        'separators': ['@', '-'],
        'terminal-punctuation': 'strict'
    }
    rendered = render_profile_definition(profile_def)
    assert isinstance(rendered, str)
    assert len(rendered) > 0


def test_render_profile_definition_with_separators_all():
    profile_def = {
        'files': 'sources.json#movies',
        'language': 'en-us',
        'fields': 3,
        'order': 'random',
        'separators': 'all',
        'terminal-punctuation': 'strict',
        'output': 'readable sentence'
    }
    rendered = render_profile_definition(profile_def)
    assert isinstance(rendered, str)
    assert len(rendered) > 0
    assert '|' not in rendered
    assert ';' not in rendered
    assert ':' not in rendered


def test_render_profile_definition_ai_sentence():
    profile_def = {
        'files': 'sources.json#movies',
        'language': 'en-us',
        'fields': 3,
        'order': 'random',
        'separators': 'all',
        'terminal-punctuation': 'strict',
        'output': 'ai sentence'
    }
    rendered = render_profile_definition(profile_def)
    assert isinstance(rendered, str)
    assert len(rendered) > 0
    assert '|' not in rendered
    assert ';' not in rendered
    assert ':' not in rendered


def test_validate_profile_definition_with_sources_json_reference():
    profile_def = {
        'files': 'sources.json#movies',
        'language': 'en-us',
        'fields': 3,
        'order': 'random',
        'separators': 'all',
        'marked-syntax': 'all',
        'output': 'readable sentence',
        'terminal-punctuation': 'strict'
    }
    validated = validate_profile_definition(profile_def)
    assert validated['language'] == 'en-us'
    assert validated['order'] == 'random'
    assert isinstance(validated['separators'], list)
    assert isinstance(validated['marked-syntax'], list)


def test_validate_profiles_file():
    validated = validate_profiles_file(Path('profiles') / 'profiles.json')
    assert 'xspace' in validated
    assert 'movies' in validated


def test_list_from_name_supports_leading_slash():
    assert list_from_name('/common/timestamps/past.json') == list_from_name('common/timestamps/past.json')


def test_estimate_profile_definition_entropy_with_fields_count():
    profile = {
        'files': {
            'past': 'common/timestamps/past.json',
            'present': 'common/timestamps/present.json',
            'future': 'common/timestamps/future.json'
        },
        'fields': 2,
        'order': 'random'
    }
    entropy = estimate_profile_definition_entropy(profile)
    assert entropy > 0


def test_profile_definition_requires_files():
    with pytest.raises(ValueError, match='Profile definition must be a dict with files'):
        estimate_profile_definition_entropy({'pattern': 'xspace/movies.action-titles.json'})


def test_list_from_name_non_json_returns_none():
    assert list_from_name('xspace/movies.action-titles') is None


def test_wildcard_directory_tokens():
    result = list_from_name('common/timestamps/*')
    assert isinstance(result, list)
    assert 'past' not in result  # deve être des strings spécifiques pas le token


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

