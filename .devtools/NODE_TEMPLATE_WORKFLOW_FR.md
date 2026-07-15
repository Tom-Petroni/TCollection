# TCollection: template node et workflow local

## Objectif

Avoir un point de depart unique pour creer un nouveau node, le tester tres vite
en local dans Nuke, puis le promouvoir proprement dans `TCollection`.

## Ce qui est maintenant recommande

### 1. Nouveau repo node

Utiliser le generateur inclus dans `TCollection`:

```powershell
python .devtools/scaffold_node_repo.py TEdgeDetect
```

Par defaut, le script:

- cree un repo sibling `..\TEdgeDetect`
- reprend le socle CPU-native de `TColorRamp`
- regenere toute la metadata pour `TEdgeDetect`
- pose un node d'exemple minimal compilable
- prepare `publish/`, `work/`, `xtask/` et la CI GitHub

Le scaffold actuel cible le socle CPU-native.
Si on veut un template CUDA/Hybrid plus tard, on fera une variante dediee a
partir de `TBlur`.

### 2. Travail local

Pour le cote "work", la meilleure base n'est pas une branche `work` permanente.
La reco officielle Git/GitHub est:

- une branche separee par changement
- plusieurs `git worktree` si tu veux plusieurs taches/checkouts en parallele

Sources officielles:

- [GitHub Flow](https://docs.github.com/en/get-started/using-github/github-flow)
- [git-worktree](https://git-scm.com/docs/git-worktree)
- [GitHub Desktop worktrees](https://docs.github.com/en/desktop/making-changes-in-a-branch/managing-worktrees-in-github-desktop)

Concretement, pour ton setup solo, je recommande:

- `main` = branche propre/livrable
- `feat/*`, `fix/*`, `chore/*` = branches courtes
- un worktree par tache locale importante

Donc au lieu de:

- une seule branche `work` longue qui finit par tout melanger

on fait plutot:

- `feat/tcolorramp-inline-ui`
- `fix/tmask-linux-loader`
- `feat/tcollection-update-panel`

et si besoin chaque branche vit dans son propre dossier local.

## Helper worktree

Tu as maintenant aussi un helper dans `TCollection`:

```powershell
pwsh .devtools/new_worktree.ps1 -RepoPath ..\TColorRamp -Name ramp-inline-ui -Branch feat/tcolorramp-inline-ui
```

Par defaut, le worktree est cree dans:

```text
..\_worktrees\<RepoName>\<Name>
```

Exemples:

```powershell
pwsh .devtools/new_worktree.ps1 -RepoPath ..\TCollection -Name promote-ramp -Branch feat/promote-ramp
pwsh .devtools/new_worktree.ps1 -RepoPath ..\TNoise -Name fast-local -Branch feat/tnoise-fast-local
```

Si tu preferes le GUI, GitHub Desktop supporte maintenant les worktrees
nativement aussi.

## Loop locale rapide recommandee

Dans un repo node scaffolded:

```powershell
cd ..\TEdgeDetect\work
cargo xtask --compile --nuke-versions 16.0 --target-platform windows --output-to-package --limit-threads
```

Le build local rapide sort dans:

```text
work/TEdgeDetect/bin/16.0/windows/x86_64/TEdgeDetect.dll
```

Pour iterer vite:

1. coder dans `work/`
2. tester le package `work/` dans Nuke
3. quand le package Python est bon, resynchroniser `publish/`

```powershell
cd ..\TEdgeDetect
python tools/sync_package_from_work.py
```

Cette separation est utile:

- `work/` = loop rapide locale
- `publish/` = package de release propre pour les artistes et la CI

## Promotion dans TCollection

Quand le node est pret:

1. release le repo node
2. dans `TCollection`:

```powershell
python tools/promote_node.py TEdgeDetect --repo-path ..\TEdgeDetect
python tools/validate_collection.py
python tools/assemble_collection.py --source github-release --statuses stable
```

3. tester la collection
4. releaser `TCollection`

## Pourquoi cette approche est meilleure qu'une branche `work` fixe

- tu ne bloques pas plusieurs sujets dans la meme branche
- tu peux garder un checkout propre pendant qu'un autre compile/teste
- tu evites le stash permanent
- tu peux ouvrir plusieurs repos/nodes en parallele sans friction
- c'est exactement le cas d'usage vise par `git worktree`
