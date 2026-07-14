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
5. un audit GitHub dedie peut verifier l'etat des repos et des releases de nodes

## Pipeline GitHub final recommande

### 1. Repo node, par exemple `TNoise`

- `pull_request` et `push` sur `main`:
  - smoke CI rapide uniquement
  - syntaxe Python
  - verification de l'outil de build
- tag `vX.Y.Z` ou `workflow_dispatch`:
  - build complet Windows + Linux
  - matrix `13.0` a `17.0`
  - assemblage du ZIP release du node
- `workflow_dispatch` avec sync explicite:
  - mise a jour optionnelle de `publish/<Node>/bin` depuis les artifacts CI

L'idee est de ne pas lancer la matrice complete a chaque push sur `main`.
On garde un feedback rapide au quotidien, et on reserve le build complet aux
releases ou aux executions manuelles.

### Repos prives

Si un node devient prive:

- le repo source du node peut rester totalement prive
- la CI du node continue de publier son zip runtime en release GitHub
- `TCollection` recupere cet asset via le secret `TCOLLECTION_NODE_REPO_TOKEN`

Cela permet de garder:

- `TCollection` public
- les updates et manifests publics de la collection
- les sources sensibles hors du repo public

### 2. Runtime node

- workflow separe sur runners self-hosted avec Nuke installe
- utile pour prouver qu'un node charge vraiment dans Nuke
- a lancer sur quelques versions cles si tu veux optimiser les couts

### 3. Repo `TCollection`

- `validate-collection.yml`:
  - regenere les fichiers derives
  - valide la coherence metadata
  - assemble une collection test depuis les releases GitHub des nodes
- `publish-collection.yml`:
  - revalide et reaudit avant publication
  - assemble `TCollection-vX.Y.Z.zip`
  - publie aussi `latest.json` et `SHA256SUMS.txt`
- `audit-node-sources.yml`:
  - surveille les repos et assets GitHub des nodes actifs

### 4. Rythme conseille

- plusieurs pushes libres sur le repo node sans gros cout CI
- une release node quand le package est pret
- une promotion dans `TCollection`
- une release collection quand tu veux livrer aux artistes

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
python tools/audit_node_sources.py --strict-enabled
python tools/validate_collection.py
python tools/assemble_collection.py --source github-release --statuses stable
```

5. commit et push sur `main`

### Standard de nommage

Le repo GitHub public d'un node doit suivre le nom du node:

- `TNormalRelight` -> `Tom-Petroni/TNormalRelight`
- `TSMAA` -> `Tom-Petroni/TSMAA`
- `TScatter` -> `Tom-Petroni/TScatter`

Le detail est documente dans `docs/NODE_REPO_STANDARD_FR.md`.

### Ce que fait `promote_node.py`

Le script:

1. lit le `node.json` du repo node
2. met a jour `nodes/registry.json`
3. regenere `config/node_lock.json`
4. regenere `tcollection/manifest.json`
5. regenere `nodes/catalog.json`
6. regenere `docs/NODE_CATALOG_FR.md`
7. valide la coherence du tout
8. peut etre suivi d'un audit GitHub des repos et releases

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

Un rapport d'audit local ou CI peut aussi etre genere dans `audit/`.

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

Si certains nodes sont prives, ce workflow peut utiliser le secret
`TCOLLECTION_NODE_REPO_TOKEN` pour telecharger leurs assets de release.

### `publish-collection.yml`

Fait:

- resynchronisation des fichiers derives
- validation stricte de la metadata collection
- audit strict des releases GitHub des nodes actifs
- assemblage depuis `github-release`
- generation du ZIP
- generation de `latest.json`
- generation de `SHA256SUMS.txt`
- publication des assets sur la release taggee

Ce workflow peut aussi utiliser `TCOLLECTION_NODE_REPO_TOKEN` pour assembler une
release `TCollection` depuis des nodes sources prives.

### `audit-node-sources.yml`

Fait:

- verification des repos GitHub de nodes
- verification des releases et assets attendus pour les nodes actifs
- upload d'un rapport d'audit en artifact GitHub Actions

Si certains nodes sont prives, ce workflow peut lui aussi utiliser
`TCOLLECTION_NODE_REPO_TOKEN` pour auditer correctement leurs releases.
