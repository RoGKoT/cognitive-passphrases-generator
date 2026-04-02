# Cognitive Passphrases Generator

## 1. Objectif

Générateur de passphrases basé sur des profils (`profiles/profiles.json`) et des listes JSON (`catalog/*`).

- `generate_passphrase.py` génère une passphrase à partir d'un profil.
- `profiles/profiles.json` définit les modèles et composants.
- `catalog/` stocke les listes de mots (JSON).
- `xspace` est un exemple de profil intégré dans ce moteur.

## 2. Prérequis

- Python 3.8+ (recommandé 3.10+)
- Aucune dépendance externe nécessaire pour le moteur principal.
- Fichier optionnel `paths.env` à la racine pour redéfinir `CATALOG`, `PROFILES`, etc.

## 3. Structure des données

### 3.1 Liste des tokens

Les listes sont stockées sous `catalog/` (fichiers JSON) :
- `catalog/xspace/movies.heroes.json`
- `catalog/common/timestamps/past.json`

Le terme « token » se réfère ici à un jeu de valeurs à choisir au hasard.

Le moteur résout un token selon ces règles (strict JSON-only) :
1. `name` doit être un chemin JSON valide (par exemple `catalog/xspace/movies.heroes.json`).
2. Les chemins de type `namespace/name.json` sont supportés (ex. `xspace/movies.heroes.json`).
3. Les tokens simples doivent explicitement pointer un fichier JSON (ex. `common/timestamps/past.json`).

Si rien n'est trouvé, le système lève `ValueError`.

### 3.2 Profils (`profiles/profiles.json`)

Format utilisé:

- objet avec `files` + `separators`.

Exemple valide :

```json
{
  "xspace": {
    "files": {
      "actions": "xspace/movies.action-titles.json",
      "heroes": "xspace/movies.heroes.json",
      "titles": "xspace/movies.titles.json",
      "timestamps": "common/timestamps/*"
    },
    "separators": ["-", "@", "."]
  }
}
```

## 4. Usage

```bash
cd y:/Projets/cognitive-passphrases-generator
python generate_passphrase.py --profile xspace
python generate_passphrase.py --profile xspace --count 3
python generate_passphrase.py --profile xspace --validate
```

Sur Windows (cmd/powershell) :

```powershell
.
\generate_passphrase.cmd --profile xspace
.
\generate_passphrase.ps1 --profile xspace
```

## 5. Options CLI

- `--profile, -p` : profil à utiliser (obligatoire)
- `--count, -n` : nombre de passphrases (défaut 1)
- `--validate` : vérifie le profil et s'arrête

## 6. Retour et classification d'entropie

Le script affiche :

`Cognitive Passphrases Generator - Actual Entropy level [XX.XX] (<niveau>)`

Niveaux :
- `very low` (< 28)
- `low` (28–39)
- `medium` (40–59)
- `high` (60–79)
- `very high` (> =80)

## 7. Comportement

- Pointeur `render_profile_definition()` traite les formats chaîne, liste, objet.
- `list_from_name()` cherche dans : 
  - `DATA_DIR/*.json`, `DATA_DIR/categories/*.json`
  - `catalog/*.json`, `catalog/categories/*.json`, via nom normalisé (`.` / `-` -> `_`)
  - `catalog/**/*` (recherche récursive)
- Si list token inconnu, levée `ValueError`.
- Séparateurs (`-`, `@`, `.`, `|`, `+`) sont rendus littéralement.

## 8. Tests

- `test_generate_passphrase.py` couvre :
  - estimation d'entropie (`estimate_*_entropy`)
  - rendu (pattern + objets `files`)
- exécution :

```bash
python -c "from test_generate_passphrase import run_all_tests; run_all_tests()"
```