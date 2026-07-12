# TCollection: standard des repos de nodes

## Principe

Chaque node doit vivre dans son propre repo GitHub.

Le standard vise a garder:

- un repo simple pour le dev du node
- une release simple a consommer depuis `TCollection`
- une convention stable pour les artistes et pour la CI

## Convention de nommage

Le repo public doit avoir le meme nom que le node:

- `TNoise` -> `Tom-Petroni/TNoise`
- `TMask` -> `Tom-Petroni/TMask`
- `TNormalRelight` -> `Tom-Petroni/TNormalRelight`

## Convention de release

- tag GitHub: `vX.Y.Z`
- asset de release: `{NodeKey}-vX.Y.Z.zip`
- racine de l'archive: `{NodeKey}-X.Y.Z`

## Base recommandee

Utiliser `NukeNodeTemplate` comme point de depart pour chaque nouveau repo node.

## Checklist de creation d'un nouveau repo node

1. creer le repo GitHub avec le nom du node
2. generer le repo depuis `NukeNodeTemplate`
3. verifier la presence de `node.json`, `VERSION` et `.github/workflows/`
4. verifier que la CI publie bien les builds Windows et Linux si le node est natif
5. publier une premiere release `vX.Y.Z`
6. verifier que l'asset `{NodeKey}-vX.Y.Z.zip` est attache a la release
7. ajouter ou verifier l'entree dans `config/node_repos.json`
8. promouvoir le node dans `TCollection` si besoin

## Contrat minimal attendu

Chaque repo node compatible `TCollection` doit exposer:

- `node.json` a la racine
- `VERSION` en `X.Y.Z`
- `publish/<NodeKey>/...`
- un tag `vX.Y.Z`
- un asset de release `{NodeKey}-vX.Y.Z.zip`

Pour les nodes natifs, le template gere aussi:

- build matrix Windows/Linux sur les versions Nuke supportees
- validation du package Python avant publication
- option de synchronisation de `publish/<NodeKey>/bin`

## Verification depuis TCollection

```powershell
python tools/audit_node_sources.py --strict-enabled
```

Ce script:

- verifie que les repos GitHub existent
- verifie que les releases des nodes actifs existent
- verifie que l'asset attendu est bien present
