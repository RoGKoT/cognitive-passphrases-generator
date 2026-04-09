# Cognitive Passphrases Generator User Manual

This manual describes how to use the current passphrase generator and the profile schema supported today.

## Getting started

1. Choose or create a profile in `profiles/profiles.json`.
2. Verify referenced JSON paths exist in `catalog/`.
3. Run the script:

```bash
python generate_passphrase.py <profile>
```

To generate multiple passphrases:

```bash
python generate_passphrase.py <profile> --count 5
```

To show generation details:

```bash
python generate_passphrase.py <profile> --details
```

6. The generator validates profiles automatically before rendering.

## Profile structure

Current profile keys:

- `files`:
  - required.
  - either a JSON object with field-to-source mappings, or a source reference string such as `sources.json#movies`.
- `separators`:
  - required.
  - object with keys:
    - `enabled`: boolean
    - `odds`: integer 0-100
    - `files`: object mapping separator keys to source paths
    - `values`: list of explicit separator strings
- `prefix`:
  - optional.
  - object with keys: `enabled`, `odds`, `files`, `values`.
- `terminal-punctuation`:
  - optional.
  - object with keys: `enabled`, `odds`, `files`, `values`.
- `space`:
  - optional.
  - object with keys: `enabled`, `odds`, `files`, `values`.
- `agents`:
  - optional.
  - metadata describing future AI generation agents.

### Supported `files` sources

- Direct catalog path: `movies/titles.json`
- Source reference: `sources.json#movies`

### Separator rules

- `separators` must be an object in the new schema.
- Explicit `values` are preserved exactly as written.
- `files` sources load additional separator candidates from the catalog.

## CLI options

- `profile`: required profile name from `profiles/profiles.json`
- `--count`, `-n`: number of passphrases to generate
- `--details`, `-d`: print generation details
- `--random`: use random field order instead of the default normal order

## Current supported workflow

1. Load profile definition.
2. Resolve each field from catalog token lists.
3. Select one value per field.
4. Build separators from the specified list.
5. Render the passphrase.
6. Print entropy metrics and output.

## Future work

These features are planned and not currently supported:

- `language` selection and localization
- field subset or count control
- `marked-syntax` and sentence templates
- enriched `output` modes such as readable or AI-style sentences
- terminal punctuation options
- AI augmentation via `--ai`

## Error handling

Common validation errors:

- unknown token or path
- unsupported profile keys
- missing `files` or `separators`

## Configuration notes

- `paths.env` can override `PROFILES` and `CATALOG`
- keep catalog and profile assets under source control for governance
