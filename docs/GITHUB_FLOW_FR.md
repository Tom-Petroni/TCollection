# TCollection: workflow GitHub

## Objectif

Avoir un cycle GitHub simple et fiable:

1. chaque node publie sa propre release
2. TCollection epingle les versions voulues
3. TCollection assemble un ZIP suite depuis les releases de nodes
4. GitHub publie la release de la collection avec:
   - le ZIP
   - `latest.json`
   - `SHA256SUMS.txt`

## Flux node -> collection

Quand un node change:

1. travailler dans le repo node
2. publier sa release `vX.Y.Z`
3. dans TCollection:

```powershell
python tools/promote_node.py TNoise
```

4. verifier:

```powershell
python tools/assemble_collection.py --source github-release --statuses stable
```

5. commit et push sur `main`

## Flux collection -> release

Pour publier la collection:

1. s'assurer que `main` est vert
2. creer un tag `vX.Y.Z`
3. pousser le tag
4. laisser `publish-collection.yml` assembler et publier les assets

## Assets publies

Une release TCollection doit contenir:

- `TCollection-vX.Y.Z.zip`
- `latest.json`
- `SHA256SUMS.txt`

## Pourquoi `latest.json`

Il permet a un updater de connaitre rapidement:

- la derniere version
- l'URL de telechargement
- l'URL des notes de release

## Pourquoi `SHA256SUMS.txt`

Il permet:

- verification d'integrite
- debug de livraison
- eventuelle verification cote updater plus tard

## CI actuelle

### `validate-collection.yml`

Verifie:

- generation deterministe des fichiers derives
- coherence metadata
- assemblage local depuis les releases GitHub des nodes

### `publish-collection.yml`

Fait:

- assemblage depuis `github-release`
- generation du ZIP
- generation de `latest.json`
- generation de `SHA256SUMS.txt`
- publication des assets sur la release taggee

