# AGENTS.md

## Purpose

This repository requires implementation work to follow the latest validated plan and recent user decisions.
The goal is to prevent scope drift, accidental reinterpretation, and destructive changes during implementation.

> Note: French is used only for our conversation with the user. All code, documentation, comments, and implementation details must remain in `en-us` to follow project standards.

## Source Of Truth

When an implementation agent starts work, it must use this priority order:

1. The latest explicit user request
2. The latest validated implementation plan discussed in the conversation
3. Repository instruction files and workspace instructions
4. The current codebase and tests
5. Earlier conversation content only if it does not conflict with items 1-4

If earlier discussion conflicts with the latest validated plan or latest user decision, it is superseded and must be ignored.

## Implementation Trigger Rules

When the user asks to "start implementation", "implement", "apply the plan", or equivalent, the agent must:

1. Identify the latest validated plan in the conversation
2. Treat that plan as binding
3. Refuse to reinterpret unresolved design questions as implementation freedom
4. Ask for clarification before coding if any blocking ambiguity remains

The agent must not take tangents into unrelated refactors, speculative redesign, or opportunistic cleanup unless the user explicitly asks for it.

## Conversation Anchoring

The agent must not wander upward in the conversation to revive abandoned ideas, old assumptions, or superseded designs.

The agent may consult earlier messages only to recover:
- exact accepted vocabulary
- explicit constraints
- examples already approved by the user
- rationale needed to resolve a direct contradiction

The agent must not use earlier messages to override newer decisions.

## Required Planning Behavior

Before editing code, the agent must produce a short implementation summary that states:

1. Which plan it is following
2. Which files it expects to touch
3. Which requirements are in scope
4. Which items are explicitly out of scope

If no stable plan exists, the agent must stop and ask for clarification instead of improvising.

## Required Change Discipline

The agent must implement the minimum coherent set of changes needed to satisfy the validated plan.

The agent must:
- fix root causes rather than patch symptoms when feasible
- preserve existing public behavior unless the plan explicitly changes it
- avoid unrelated formatting churn
- avoid renaming unrelated symbols
- avoid deleting user work
- avoid destructive git commands
- avoid reverting changes it did not make

## Profile Engine Specific Rules

For this repository, profile-driven behavior must be implemented from explicit profile semantics, not guessed from field names.

If a profile key has documented or user-defined semantics, the agent must implement exactly those semantics.

For profile changes:
- `order` controls field ordering strategy
- `separators` controls valid separators and separator source resolution

If any of these semantics are unclear at implementation time, the agent must ask before coding.

## Strict Anti-Drift Rules

The agent must not:
- add features adjacent to the request "while it is there"
- silently change the schema
- replace validated semantics with a "better" interpretation
- update documentation to describe behavior that was not actually implemented
- infer hidden requirements from comments if they conflict with the approved plan

## Validation Requirements

After implementation, the agent must validate the change with the smallest relevant verification set, for example:

1. targeted unit tests
2. profile validation commands
3. smoke execution for affected profiles
4. lint or type checks only if relevant to changed code

If validation cannot be run, the agent must say so explicitly.

## Reporting Requirements

At the end of implementation, the agent must report:

1. what was implemented
2. which files were changed
3. what was validated
4. any unresolved risks or deferred decisions

The report must distinguish:
- completed behavior
- assumptions
- not implemented items

## Ambiguity Protocol

If the user gives a partial plan and some semantics are still undecided, the agent must:

1. stop before code edits
2. list the blocking ambiguities
3. ask only the minimum required questions
4. resume only after clarification

The agent must not convert ambiguity into silent assumptions.

## Preferred Working Mode For This Repository

Implementation should follow this sequence:

1. read current code and tests
2. align with the latest validated plan
3. make minimal focused edits
4. add or update targeted tests
5. validate
6. report precisely

## Repository Safety Rule

For this repository, the latest validated plan is the working contract.
If the agent detects tension between older conversation content and the latest plan, the latest plan wins.

## À considérer

### 1. Refus explicite des refactors non demandés
Le mode implémentation doit interdire tout refactor hors périmètre validé.
Tout refactor opportuniste doit être proposé séparément, jamais inclus automatiquement.

### 2. Checklist obligatoire avant toute édition
Avant le premier changement, l’agent doit confirmer :
- le plan de référence retenu
- les fichiers ciblés
- les exigences en scope
- les exigences hors scope
- les points ambigus restants
Si un point est ambigu, l’agent doit s’arrêter et poser la question avant de coder.

### 3. Section anti-crash spécifique au moteur de profils
Pour `language`, `fields`, `order`, `separators`, `marked-syntax`, `output`, `terminal-punctuation` :
- aucune sémantique implicite
- aucune extension non validée
- validation stricte des types et valeurs
- tests ciblés obligatoires pour chaque mode ajouté
- arrêt immédiat si la configuration profil est invalide