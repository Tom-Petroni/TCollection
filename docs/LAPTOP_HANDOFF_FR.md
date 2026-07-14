# Reprise Sur PC Portable

Ce document permet de reprendre rapidement le travail sur un autre PC a partir
de GitHub, sans dependre de l'etat local de cette machine.

## Etat valide au 14 juillet 2026

Releases confirmees:

- `TColorRamp` : `v1.0.2`
- `TCollection` : `v0.1.18`

Versions stables actuellement epinglees dans `TCollection`:

- `TBlur` : `1.0.6`
- `TColorRamp` : `1.0.2`
- `TMask` : `0.1.3`
- `TNoise` : `2.1.3`

Releases utiles:

- `TCollection` : `https://github.com/Tom-Petroni/TCollection/releases/tag/v0.1.18`
- `TColorRamp` : `https://github.com/Tom-Petroni/TColorRamp/releases/tag/v1.0.2`

## Repos a cloner

Pour garder le workflow local `promote_node.py`, il faut cloner les repos comme
des repos freres dans un meme dossier parent.

Exemple de layout:

```text
Dev/
  TCollection/
  TBlur/
  TColorRamp/
  TMask/
  TNoise/
```

Commandes exemple:

```powershell
mkdir C:\Dev\tsuite
cd C:\Dev\tsuite
git clone https://github.com/Tom-Petroni/TCollection.git
git clone https://github.com/Tom-Petroni/TBlur.git
git clone https://github.com/Tom-Petroni/TColorRamp.git
git clone https://github.com/Tom-Petroni/TMask.git
git clone https://github.com/Tom-Petroni/TNoise.git
```

Ce layout correspond a `config/dev_sources.json` dans `TCollection`.

## Reprise rapide

Depuis un clone frais de `TCollection`:

```powershell
cd C:\Dev\tsuite\TCollection
python tools\validate_collection.py
python tools\assemble_collection.py --source github-release --statuses stable --package-version 0.1.18 --output dist_portable
```

Ce test doit assembler une collection avec:

- `TBlur`
- `TColorRamp`
- `TMask`
- `TNoise`

## Workflow normal pour mettre a jour un node

Exemple si tu modifies `TColorRamp`:

1. travailler dans le repo `TColorRamp`
2. mettre a jour le code
3. bump la version du node
4. publier la release GitHub du node
5. revenir dans `TCollection`
6. promouvoir le node

Commandes:

```powershell
cd C:\Dev\tsuite\TCollection
python tools\promote_node.py TColorRamp
python tools\validate_collection.py
python tools\assemble_collection.py --source github-release --statuses stable
```

Fichiers automatiquement mis a jour:

- `nodes/registry.json`
- `config/node_lock.json`
- `tcollection/manifest.json`
- `nodes/catalog.json`
- `docs/NODE_CATALOG_FR.md`

## Workflow normal pour sortir une nouvelle collection

Quand les versions de nodes voulues sont epinglees:

```powershell
cd C:\Dev\tsuite\TCollection
python tools\bump_collection_version.py --bump patch
python tools\sync_manifest.py
python tools\validate_collection.py
python tools\assemble_collection.py --source github-release --statuses stable
git add VERSION config/collection.json config/node_lock.json nodes/registry.json nodes/catalog.json docs/NODE_CATALOG_FR.md tcollection/manifest.json
git commit -m "release: TCollection X.Y.Z"
git push origin main
git tag -a vX.Y.Z -m "TCollection vX.Y.Z"
git push origin vX.Y.Z
```

Important:

- faire le `commit` avant de creer le tag
- ne pas lancer le `commit` et le `tag` en parallele
- le publish GitHub de `TCollection` se declenche depuis le tag

## Fichiers et scripts importants

Dans `TCollection`:

- `tools/promote_node.py`
- `tools/assemble_collection.py`
- `tools/validate_collection.py`
- `tools/bump_collection_version.py`
- `config/dev_sources.json`
- `config/node_lock.json`
- `nodes/registry.json`
- `tcollection/manifest.json`

Dans `TColorRamp`:

- `node.json`
- `VERSION`
- `.github/workflows/nuke-build.yml`
- `.github/workflows/version-tag.yml`
- `config/nuke_versions.json`
- `node_build_config.json`

## Ecart local a connaitre

Ces elements ne sont pas necessairement pushes dans GitHub et peuvent ne pas
exister sur le portable apres clone:

### TCollection

- un `README.md` localement modifie
- plusieurs dossiers `dist_*` de test local

Ils peuvent etre ignores pour reprendre proprement.

### TColorRamp

- `.github/workflows/nuke-runtime-smoke.yml` est encore modifie localement sur
  cette machine

Ce changement n'est pas requis pour reprendre le flux principal CI/release.

## Dernier point connu

La chaine valide la plus recente est:

1. `TColorRamp v1.0.1` publie et vert
2. `TCollection v0.1.17` publie avec `TColorRamp 1.0.1`

Si tu veux reprendre la suite sur le portable, le point de depart recommande est:

```powershell
cd C:\Dev\tsuite\TCollection
python tools\validate_collection.py
```

Puis choisir:

- soit travailler sur un node repo
- soit preparer une nouvelle release collection
