#!/usr/bin/env python3
import argparse
import json
import math
import os
import random
import re
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent

# Load overrides from paths.env (optional)
def load_paths_env(path):
    if not path.exists():
        return {}
    vars = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            continue
        k, v = line.split('=', 1)
        k = k.strip().lstrip('$')
        v = v.strip()
        # Support windows path escaping and env expansion
        v = v.replace('\\', os.sep)
        v = os.path.expandvars(v)
        vars[k] = v
    return vars

_path_vars = load_paths_env(DATA_DIR / 'paths.env')
PROFILE_DIR = Path(_path_vars.get('PROFILES', DATA_DIR / 'profiles'))
PROFILE_FILE = PROFILE_DIR / 'profiles.json'
CATALOG_DIR = Path(_path_vars.get('CATALOG', DATA_DIR / 'catalog'))

random_generator = random.SystemRandom()

def load_profiles(path):
    text = path.read_text(encoding='utf-8').strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        profiles = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if ':' not in line:
                continue
            key, value = line.split(':', 1)
            profiles[key.strip()] = value.strip()
        return profiles


def list_from_name(list_name):
    stable_name = list_name.strip()
    if not stable_name:
        return None

    if '..' in stable_name:
        raise ValueError(f'Invalid list token: {stable_name}')

    # Strict mode: tokens must be explicit JSON paths or wildcard directories
    if stable_name.endswith('/*'):
        prefix = stable_name[:-2]
        values = []

        # If prefix is a relative path, include matching catalog/ and PRODUCTS dir
        for base in [DATA_DIR / prefix, CATALOG_DIR / prefix]:
            if base.exists() and base.is_dir():
                for file in base.glob('*.json'):
                    values.extend(json.loads(file.read_text(encoding='utf-8')))

        # Also support category-style shorthands with categories/ prefix
        for base_parent in [DATA_DIR / 'categories', CATALOG_DIR / 'categories']:
            candidate = base_parent / prefix
            if candidate.exists() and candidate.is_dir():
                for file in candidate.glob('*.json'):
                    values.extend(json.loads(file.read_text(encoding='utf-8')))

        return values if values else None

    if not stable_name.endswith('.json'):
        return None

    candidate_paths = [
        DATA_DIR / stable_name,
        DATA_DIR / 'categories' / stable_name,
        CATALOG_DIR / stable_name,
        CATALOG_DIR / 'categories' / stable_name,
    ]

    for candidate in candidate_paths:
        if candidate.exists():
            return json.loads(candidate.read_text(encoding='utf-8'))

    return None


def tokenize_expression(expr):
    parts = re.split(r'([@\-\|\+]+)', expr)
    tokens = []
    for part in parts:
        if part == '':
            continue
        if re.fullmatch(r'[@\-\|\+]+', part):
            tokens.append(part)
            continue
        # Keep . as separator only when token is not a path (no slash)
        if '.' in part and '/' not in part:
            subparts = re.split(r'(\.)', part)
            tokens.extend([s for s in subparts if s != ''])
        else:
            tokens.append(part)
    return tokens


def render_expression(expr, strict=False):
    tokens = tokenize_expression(expr)
    output = []
    for token in tokens:
        if re.fullmatch(r'[@\-\.\|\+]+', token):
            output.append(token)
            continue

        values = list_from_name(token)
        if values is None:
            raise ValueError(f"Unknown list token: '{token}' in expression '{expr}'")

        output.append(str(random_generator.choice(values)))
    return ''.join(output)


def render_parts(parts, strict=False):
    if not isinstance(parts, list):
        raise ValueError('parts must be a list')
    output = []
    for item in parts:
        if not isinstance(item, str):
            raise ValueError('parts must contain string tokens only')
        if re.fullmatch(r'[@\-\.\|\+]+', item):
            output.append(item)
            continue
        values = list_from_name(item)
        if values is None:
            raise ValueError(f"Unknown list token: '{item}' in parts")
        output.append(str(random_generator.choice(values)))
    return ''.join(output)


def render_template(template, strict=False):
    def replacement(match):
        key = match.group(1)
        values = list_from_name(key)
        if values is None:
            raise ValueError(f"Unknown template token: '{{{key}}}'")
        return str(random_generator.choice(values))

    return re.sub(r"\{([^}]+)\}", replacement, template)


def render_profile_definition(profile_def, strict=False):
    if not isinstance(profile_def, dict):
        raise ValueError('Profile definition must be an object with files')

    files = profile_def.get('files')
    if not isinstance(files, dict) or not files:
        raise ValueError('Profile object must contain "files" with at least one entry')

    separators = profile_def.get('separators', [])
    if not isinstance(separators, list):
        raise ValueError('separators must be a list')

    keys = list(files.keys())
    requested_parts = []
    for token in keys:
        source = files[token]
        if not isinstance(source, str):
            raise ValueError('file references must be string list tokens or paths')
        values = list_from_name(source)
        if values is None:
            raise ValueError(f"Unknown list token/path: '{source}' in profile files")
        requested_parts.append(str(random_generator.choice(values)))

    separator_values = []
    if separators:
        if len(separators) == 1:
            separator_values = [separators[0]] * max(len(requested_parts) - 1, 0)
        else:
            separator_values = [separators[i % len(separators)] for i in range(max(len(requested_parts) - 1, 0))]

    result = []
    for i, part in enumerate(requested_parts):
        result.append(part)
        if i < len(separator_values):
            result.append(separator_values[i])
    return ''.join(result)


def estimate_expression_entropy(expr):
    if not isinstance(expr, str):
        raise ValueError('Expression entropy can only be calculated for string expressions')

    bits = 0.0
    tokens = tokenize_expression(expr)
    for token in tokens:
        if re.fullmatch(r'[@\-\.\|\+]+', token):
            continue
        values = list_from_name(token)
        if values:
            try:
                n = len(values)
            except TypeError:
                n = 1
            if n > 0:
                bits += math.log2(n)
    return bits


def estimate_parts_entropy(parts):
    if not isinstance(parts, list):
        raise ValueError('Parts entropy can only be calculated for list parts')

    bits = 0.0
    for item in parts:
        if not isinstance(item, str):
            raise ValueError('Parts must contain string tokens only')
        if re.fullmatch(r'[@\-\.\|\+]+', item):
            continue
        values = list_from_name(item)
        if values:
            try:
                n = len(values)
            except TypeError:
                n = 1
            if n > 0:
                bits += math.log2(n)
    return bits


def estimate_template_entropy(template):
    if not isinstance(template, str):
        raise ValueError('Template entropy can only be calculated for a template string')

    bits = 0.0
    for match in re.finditer(r'{([^}]+)}', template):
        key = match.group(1)
        values = list_from_name(key)
        if values:
            try:
                n = len(values)
            except TypeError:
                n = 1
            if n > 0:
                bits += math.log2(n)
    return bits


def estimate_profile_definition_entropy(profile_def):
    if isinstance(profile_def, dict) and 'files' in profile_def and isinstance(profile_def['files'], dict):
        files = profile_def['files']
        entropy = 0.0
        for key in files:
            source = files[key]
            if not isinstance(source, str):
                raise ValueError('file references must be string list tokens or paths')
            values = list_from_name(source)
            if values is None:
                raise ValueError(f"Unknown list token/path: '{source}' in profile files")
            n = len(values) if hasattr(values, '__len__') else 1
            if n > 0:
                entropy += math.log2(n)
        return entropy

    raise ValueError('Profile definition must be a dict with files')


def classify_entropy(entropy_bits):
    if entropy_bits < 28:
        return 'very low'
    if entropy_bits < 40:
        return 'low'
    if entropy_bits < 60:
        return 'medium'
    if entropy_bits < 80:
        return 'high'
    return 'very high'


def main():
    parser = argparse.ArgumentParser(description='Generate passphrases using profiles.json patterns.')
    parser.add_argument('--profile', '-p', required=True, help='Profile name defined in profiles.json')
    parser.add_argument('--count', '-n', type=int, default=1, help='How many passphrases to generate')
    parser.add_argument('--validate', action='store_true', help='Validate profile, then exit without generating')

    if len(sys.argv) == 1:
        print('=== xSpace Passphrase Generator ===')
        print('Run from PowerShell/cmd with:')
        print('  python generate_passphrase.py --profile xspace --count 1')
        print('')
        print('Usage: python generate_passphrase.py --profile PROFILE [--count N] [--validate]')
        print('Example: python generate_passphrase.py --profile xspace --count 2')
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    profiles = {k.lower(): v for k, v in load_profiles(PROFILE_FILE).items()}
    profile_name = args.profile.lower()
    if profile_name not in profiles:
        raise SystemExit(f'Error: profile "{args.profile}" not found in {PROFILE_FILE}')
    profile_def = profiles[profile_name]

    if args.validate:
        try:
            rendered = render_profile_definition(profile_def)
            print('Validation successful:', rendered)
            return
        except Exception as ex:
            raise SystemExit(f'Validation failed: {ex}')

    entropy_bits = estimate_profile_definition_entropy(profile_def)
    entropy_label = classify_entropy(entropy_bits)
    print(f'Cognitive Passphrases Generator - Actual Entropy level [{entropy_bits:.2f}] ({entropy_label})')

    for _ in range(args.count):
        print(render_profile_definition(profile_def))


if __name__ == '__main__':
    main()
