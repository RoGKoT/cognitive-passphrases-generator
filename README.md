# Cognitive Passphrases Generator

## 1. Purpose

A profile-driven passphrase generator based on `profiles/profiles.json` and JSON lists under `catalog/*`.

- `generate_passphrase.py` builds a passphrase from a profile.
- `profiles/profiles.json` defines patterns and components.
- `catalog/` stores value lists and vocabulary files.
- `xspace` is an example built-in profile.

## 2. Requirements

- Python 3.10+ (recommended)
- Poetry for dependency management (optional)

## 2.1 Installation

### Basic installation (no extra dependencies)

Clone the repository and run directly:

```bash
git clone <repository-url>
cd cognitive-passphrases-generator
python generate_passphrase.py xspace
```

### Installation with Poetry (recommended for development)

```bash
git clone <repository-url>
cd cognitive-passphrases-generator
poetry install
poetry run python generate_passphrase.py xspace
```

### Installation with pip

```bash
pip install -e .
```

## 2.2 Development

To contribute to the project:

1. Install development dependencies: `poetry install`
2. Run tests: `poetry run pytest`
3. Run linting: `poetry run ruff check .`
4. Check types: `poetry run mypy generate_passphrase.py`
5. Run security checks: `poetry run bandit -r generate_passphrase.py`

## 3. Data structure

### 3.1 Token lists

Value lists are stored under `catalog/` as JSON files:
- `catalog/movies/actions/en-us.json`
- `catalog/common/timestamps/past.json`
- `catalog/common/vocabulary/separators.json`
- `catalog/common/vocabulary/sentence_templates.json`
- `catalog/common/vocabulary/grammar.json`
- `catalog/common/vocabulary/phrase_modifiers.json`

A token refers to a set of values chosen at random.

The generator resolves a token using these rules (JSON-only):
1. `name` must be a valid JSON path, such as `catalog/common/timestamps/past.json`.
2. Namespace-style paths are supported, e.g. `movies/actions/*` or `xspace/movies.heroes.json`.
3. Simple tokens must explicitly point to a JSON file, e.g. `common/timestamps/past.json`.
4. Wildcards like `/*` load all JSON files in the target directory.

If no match is found, the generator raises `ValueError`.

### 3.2 Profiles (`profiles/profiles.json`)

A profile is an object that may include several configuration keys:
- `files`: object with token definitions or a reference like `sources.json#movies`
- `language`: language code (`en-us`, `fr-ca`, `fr-fr`, `all`)
- `fields`: `all`, a positive integer, or a list of field names
- `order`: `random`, `ascending`, `descending`, `strict`
- `separators`: list or `all`
- `marked-syntax`: `all` or a specific style
- `output`: `strict`, `readable sentence`, `ai sentence`
- `terminal-punctuation`: `sentence mood`, `none`, `random`, `strict`

Valid example:

```json
{
  "movies": {
    "files": "sources.json#movies",
    "language": "en-us",
    "fields": 6,
    "order": "random",
    "separators": "all",
    "marked-syntax": "all",
    "output": "readable sentence",
    "terminal-punctuation": "sentence mood"
  }
}
```

### 3.3 Profile validation

The `profiles/validation.py` module exposes:
- `validate_profile_definition(profile_def)`
- `validate_profiles_file(path)`

Use these functions to verify that a profile is valid before generation.

## 4. Usage

```bash
cd y:/Projets/cognitive-passphrases-generator
python generate_passphrase.py xspace
python generate_passphrase.py movies --count 3
python generate_passphrase.py movies --validate
```

The output mode is defined only in the profile (`output`) and cannot be overridden on the command line.

See `USER_MANUAL.md` for the complete usage guide, profile structure, and supported values.

## 6. CLI options

- `profile`: required positional argument, the profile name defined in `profiles.json`
- `--profile, -p`: optional alias for specifying the profile with a named flag
- `--count, -n`: number of passphrases (default 1)
- `--validate`: validate the profile and exit without generating

## 7. Output and entropy classification

The script prints:

`Cognitive Passphrases Generator - Actual Entropy level [XX.XX] (<level>)`

Entropy levels:
- `very low` (< 28)
- `low` (28–39)
- `medium` (40–59)
- `high` (60–79)
- `very high` (>= 80)

## 8. Behavior

- `render_profile_definition()` processes profiles and selects values from JSON files.
- `build_readable_sentence()` uses templates and grammar rules to produce natural sentences.
- `output: "readable sentence"` generates a structured sentence without raw source separators.
- `output: "ai sentence"` enriches the sentence with style modifiers and prefixes.
- `list_from_name()` searches in:
  - `DATA_DIR/*.json`, `DATA_DIR/categories/*.json`
  - `CATALOG_DIR/*.json`, `CATALOG_DIR/categories/*.json`
  - `catalog/**/*` recursively
- `separators: all` now uses `catalog/common/vocabulary/separators.json`.

## 8. Contribution

### Contribution guide

We welcome contributions. Please follow these steps:

1. Fork the repository
2. Create a branch for your feature: `git checkout -b feature/AmazingFeature`
3. Commit your changes: `git commit -m 'Add some AmazingFeature'`
4. Push the branch: `git push origin feature/AmazingFeature`
5. Open a pull request

### Code standards

- Follow PEP 8 style
- Add type hints for functions
- Write Google-style docstrings
- Add tests for new features
- Ensure tests pass and code is linted

### Tests

Run tests with:

```bash
poetry run pytest
```

Target coverage: 80%+

### Linting and type checks

```bash
poetry run ruff check .
poetry run ruff format .
poetry run mypy generate_passphrase.py
```
## 8. Tests

- `test_generate_passphrase.py` covers:
  - entropy estimation (`estimate_*_entropy`)
  - rendering (pattern + `files` objects)
- execution:

```bash
python -c "from test_generate_passphrase import run_all_tests; run_all_tests()"
```