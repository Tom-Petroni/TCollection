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
   - un catalogue de nodes et de liens a jour dans le repo

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
python tools/sync_node_lock.py
python tools/sync_manifest.py
python tools/sync_node_catalog.py
python tools/validate_collection.py
python tools/assemble_collection.py --source github-release --statuses stable
```

5. commit et push sur `main`

### Ce que fait `promote_node.py`

Le script:

1. lit le `node.json` du repo node
2. met a jour `nodes/registry.json`
3. regenere `config/node_lock.json`
4. regenere `tcollection/manifest.json`
5. regenere `nodes/catalog.json`
6. regenere `docs/NODE_CATALOG_FR.md`
7. valide la coherence du tout

### Cas concret: mise a jour de `TNoise`

Dans `TNoise`:

1. coder
2. merger sur la branche voulue
3. laisser la CI compiler et publier `vX.Y.Z`

Dans `TCollection`:

```powershell
python tools/promote_node.py TNoise
git diff
git add .
git commit -m "feat: promote TNoise vX.Y.Z"
git push origin main
```

Ensuite, quand tu veux sortir une version collection:

```powershell
python tools/bump_collection_version.py 0.1.2
git add VERSION config/collection.json
git commit -m "chore: bump version to 0.1.2"
git tag v0.1.2
git push origin main --tags
```

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

Le repo TCollection doit aussi garder a jour:

- `config/node_lock.json`
- `tcollection/manifest.json`
- `nodes/catalog.json`
- `docs/NODE_CATALOG_FR.md`

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
- coherence du catalogue de nodes et de leurs liens GitHub

### `publish-collection.yml`

Fait:

- assemblage depuis `github-release`
- generation du ZIP
- generation de `latest.json`
- generation de `SHA256SUMS.txt`
- publication des assets sur la release taggee
