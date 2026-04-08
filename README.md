# Cognitive Passphrases Generator

A local-first passphrase generator built from JSON catalogs and profile definitions.

## Install

### Requirements

- Python 3.10 or later
- Optional: Poetry for development

### Install from source

```bash
git clone <repository-url>
cd cognitive-passphrases-generator
python generate_passphrase.py xspace
```

### Install in editable mode

```bash
pip install -e .
```

### Install with Poetry

```bash
git clone <repository-url>
cd cognitive-passphrases-generator
poetry install
poetry run python generate_passphrase.py xspace
```

## Quick start

Generate a passphrase from the built-in `xspace` profile:

```bash
python generate_passphrase.py xspace
```

Print generation details:

```bash
python generate_passphrase.py xspace --details
```

## CLI reference

```bash
python generate_passphrase.py PROFILE [--count N] [--details] [--random]
```

Supported options:

- `PROFILE`: profile name defined in `profiles/profiles.json`
- `--count`, `-n`: number of passphrases to generate (default: `1`)
- `--details`, `-d`: print generation details for fields, separators, and entropy
- `--random`: use random field order instead of the default normal order

Validation is performed automatically before passphrase rendering.

Reserved future flags:

- `--ai <name:API_KEY>`: AI augmentation
- `--ai <language:code>`: AI language target
- AI marked-syntax
- AI terminal_punctuation:>

## Profile model

Profiles are defined in `profiles/profiles.json` as a JSON object.

Each profile currently supports these keys:

- `files`: object mapping fields to token sources, or a source reference string such as `sources.json#movies`
- `separators`: a list of separator strings, or the value `all` to load `catalog/common/separators.json`

Example profile:

```json
{
  "xspace": {
    "files": {
      "actors": "movies/peoples/actors.json",
      "titles": "movies/titles.json"
    },
    "separators": [" ", "-"]
  }
}
```

## Current behavior

- `files` resolves catalog token lists and selects one value per field.
- `separators` defines how selected values are joined.
- `order: normal` preserves the profile field order.
- `order: random` shuffles fields before rendering.
- Entropy is estimated from the selected token lists, the order mode, and separators.

## Future work

The following profile capabilities are planned but not implemented yet:

- `language` selection for localized token resolution
- `fields` count or explicit field selection
- richer `output` modes such as readable or AI-style sentences
- `marked-syntax` templates and sentence modifiers
- `terminal-punctuation` control

## Configuration

- `profiles.json` is loaded from `profiles/`
- `catalog/` contains the token source JSON files
- `paths.env` can override `PROFILES` and `CATALOG`

## Documentation site

The project documents are available under `docs/`.

- Home: `docs/index.md`
- User manual: `docs/USER_MANUAL.md`
- Changelog: `docs/changelog.md`

## Contribution

1. Fork the repository.
2. Create a branch: `git checkout -b feature/<name>`.
3. Add tests and documentation.
4. Commit with a clear message.
5. Open a pull request.
