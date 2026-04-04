# User Manual

This manual explains how to use the generator, how to create a profile, and which values are supported.

## 1. Getting started

1. Choose or create a profile in `profiles/profiles.json`.
2. Verify that file paths and tokens exist in `catalog/*`.
3. Run the script:

```bash
python generate_passphrase.py <profile>
```

4. To generate multiple passphrases at once:

```bash
python generate_passphrase.py <profile> --count 5
```

5. To validate a profile without generating output:

```bash
python generate_passphrase.py <profile> --validate
```

## 2. Profile structure

A profile contains configuration keys. Supported values are:

- `files`:
  - a JSON object describing fields and tokens.
  - a reference to another JSON file or fragment, e.g. `sources.json#movies`.
- `language`:
  - `en-us`
  - `fr-ca`
  - `fr-fr`
  - `all`
- `fields`:
  - `all`: all available fields.
  - a positive integer: number of tokens to select.
  - a list of explicit field names.
- `order`:
  - `random`: random order.
  - `ascending`: ascending order.
  - `descending`: descending order.
  - `strict`: source order.
- `separators`:
  - `all`: use the shared vocabulary from `catalog/common/vocabulary/separators.json`.
  - an explicit list of separator strings.
- `marked-syntax`:
  - `all`: apply all supported syntax styles.
  - a specific supported style.
- `output`:
  - `strict`: raw token output with original separators.
  - `readable sentence`: natural sentence formatting.
  - `ai sentence`: enriched sentence styling.
- `terminal-punctuation`:
  - `sentence mood`: punctuation chosen to match sentence tone.
  - `none`: no final punctuation.
  - `random`: random punctuation.
  - `strict`: strict punctuation defined by the profile.

## 3. Example profiles

### Readable profile

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

### AI-style profile

```json
{
  "movies": {
    "files": "sources.json#movies",
    "language": "en-us",
    "fields": 6,
    "order": "random",
    "separators": "all",
    "marked-syntax": "all",
    "output": "ai sentence",
    "terminal-punctuation": "sentence mood"
  }
}
```

## 4. Glossary and supported values

- `profile`: a set of rules in `profiles/profiles.json` that controls generation.
- `token`: a list of words or symbols loaded from a JSON file.
- `fields`: the number of tokens selected or a list of field names, e.g. `6` or `["actor", "action"]`.
- `order`: one of `random`, `ascending`, `descending`, `strict`.
- `separators`: `all` or a custom list such as `["-", "@", "|"]`.
- `marked-syntax`: `all` or a supported syntax style.
- `output`: one of `strict`, `readable sentence`, `ai sentence`.
- `terminal-punctuation`: one of `sentence mood`, `none`, `random`, `strict`.
- `strict`: literal output mode.
- `readable sentence`: structured sentence mode.
- `ai sentence`: creative enriched sentence mode.
- `entropy`: security score classified as `very low`, `low`, `medium`, `high`, `very high`.

## 5. Common errors

- `ValueError`: unknown token or JSON path.
- Invalid profile: missing key or unsupported value.
- Invalid `language`: use `en-us`, `fr-ca`, `fr-fr`, or `all`.
- Missing `output`: must be `strict`, `readable sentence`, or `ai sentence`.
