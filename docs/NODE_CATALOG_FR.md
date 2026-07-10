# TCollection: catalogue des nodes

Ce document est genere depuis `nodes/registry.json`, `config/node_repos.json`
et `config/node_lock.json`.

## Nodes actifs dans la collection

| Node | Version | Status | Repo | Releases | Asset |
| --- | --- | --- | --- | --- | --- |
| TBlur | 1.0.0 | stable | [Tom-Petroni/TBlur](https://github.com/Tom-Petroni/TBlur) | [releases](https://github.com/Tom-Petroni/TBlur/releases) | `TBlur-v1.0.0.zip` |
| TColorRamp | 1.0.0 | stable | [Tom-Petroni/TColorRamp](https://github.com/Tom-Petroni/TColorRamp) | [releases](https://github.com/Tom-Petroni/TColorRamp/releases) | `TColorRamp-v1.0.0.zip` |
| TMask | 0.1.0 | stable | [Tom-Petroni/TMask](https://github.com/Tom-Petroni/TMask) | [releases](https://github.com/Tom-Petroni/TMask/releases) | `TMask-v0.1.0.zip` |
| TNoise | 2.0.1 | stable | [Tom-Petroni/TNoise](https://github.com/Tom-Petroni/TNoise) | [releases](https://github.com/Tom-Petroni/TNoise/releases) | `TNoise-v2.0.1.zip` |

## Nodes suivis mais pas encore embarques

| Node | Version | Status | Repo cible | Notes |
| --- | --- | --- | --- | --- |
| BrushScatter | 0.1.0 | test | [Tom-Petroni/BrushScatter](https://github.com/Tom-Petroni/BrushScatter) | Still in validation. |
| OnlyRender | 1.0.0 | hold | [Tom-Petroni/OnlyRender](https://github.com/Tom-Petroni/OnlyRender) | Collection-level toolset without node creation. |
| PRefToMotion | 0.1.0 | hold | [Tom-Petroni/PRefToMotion](https://github.com/Tom-Petroni/PRefToMotion) | Kept out of the default collection menu. |
| TNormalRelight | 0.1.0 | stable | [Tom-Petroni/TNormalRelight](https://github.com/Tom-Petroni/TNormalRelight) | Prepared for later activation in the collection lock. |
| TSMAA | 0.1.0 | test | [Tom-Petroni/TSMAA](https://github.com/Tom-Petroni/TSMAA) | Still in validation. |
| TScatter | 0.1.0 | test | [Tom-Petroni/TScatter](https://github.com/Tom-Petroni/TScatter) | Still in validation. |

## Mise a jour rapide d'un node

Exemple avec `TNoise`:

```powershell
python tools/promote_node.py TNoise
python tools/sync_node_lock.py
python tools/sync_manifest.py
python tools/sync_node_catalog.py
python tools/audit_node_sources.py --strict-enabled
python tools/validate_collection.py
python tools/assemble_collection.py --source github-release --statuses stable
```

Un audit GitHub plus complet peut etre genere avec
`python tools/audit_node_sources.py --strict-enabled`.

