import math
import pytest

from generate_passphrase import (
    estimate_expression_entropy,
    estimate_parts_entropy,
    estimate_template_entropy,
    estimate_profile_definition_entropy,
    list_from_name,
    render_profile_definition,
)


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
            'actions': 'xspace/movies.action-titles.json',
            'heroes': 'xspace/movies.heroes.json',
            'titles': 'xspace/movies.titles.json'
        },
        'separators': ['-', '@']
    }
    expected = (math.log2(len(list_from_name('xspace/movies.action-titles.json'))) +
                math.log2(len(list_from_name('xspace/movies.heroes.json'))) +
                math.log2(len(list_from_name('xspace/movies.titles.json'))))
    assert math.isclose(estimate_profile_definition_entropy(profile), expected, rel_tol=1e-9)


def test_render_profile_definition_produces_string():
    profile_def = {
        'files': {
            'actions': 'xspace/movies.action-titles.json',
            'heroes': 'xspace/movies.heroes.json',
            'titles': 'xspace/movies.titles.json'
        },
        'separators': ['-', '@']
    }
    rendered = render_profile_definition(profile_def)
    assert isinstance(rendered, str)
    assert '-' in rendered and '@' in rendered


def test_render_profile_definition_with_file_object_sets_separators():
    profile_def = {
        'files': {
            'actions': 'xspace/movies.action-titles.json',
            'heroes': 'xspace/movies.heroes.json',
            'titles': 'xspace/movies.titles.json'
        },
        'separators': ['-', '@']
    }
    rendered = render_profile_definition(profile_def)
    assert isinstance(rendered, str)
    assert '-' in rendered and '@' in rendered


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

