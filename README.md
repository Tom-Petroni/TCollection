# TCollection

TCollection is the central Nuke collection product for Tom Petroni tools.

It is not the main place where native nodes are authored. Each node can keep its
own repository, CI, and release cadence. TCollection is the product layer that:

- presents a single menu and installation entry point to artists
- pins exact node versions through a collection lockfile
- assembles a coherent suite from independent node releases
- prepares future in-app update notifications for artists

## Core idea

Use two levels of repositories:

- node repositories such as `TNoise`, `TBlur`, `TMask`
- one central collection repository: `TCollection`

This keeps node development simple while giving artists a single package to
install and update.

## Active node links

Current nodes shipped through the collection:

- [TBlur](https://github.com/Tom-Petroni/TBlur)
- [TColorRamp](https://github.com/Tom-Petroni/TColorRamp)
- [TMask](https://github.com/Tom-Petroni/TMask)
- [TNoise](https://github.com/Tom-Petroni/TNoise)

The generated catalog lives in [docs/NODE_CATALOG_FR.md](docs/NODE_CATALOG_FR.md).

## Repository layout

```text
TCollection/
  .github/workflows/    # collection validation and future packaging workflows
  config/               # collection settings + node repo mapping + lockfile
  docs/                 # architecture and updater strategy
  gizmos/               # collection-level gizmos
  nodes/                # registry only in source repo, payloads in packaged builds
  scripts/              # collection-level Python tools for artists
  tcollection/          # runtime loader, menu, updater, manifest
  tools/                # sync and validation helpers
  init.py               # Nuke entrypoint
  menu.py               # Nuke menu entrypoint
  VERSION               # collection version
```

## Development flow

If you update `TNoise`:

1. work in the `TNoise` repo
2. release `TNoise vX.Y.Z`
3. promote the node into TCollection:

```powershell
python tools/promote_node.py TNoise
python tools/sync_node_lock.py
python tools/sync_manifest.py
python tools/sync_node_catalog.py
python tools/validate_collection.py
```

4. optionally assemble a local collection package:

```powershell
python tools/assemble_collection.py --statuses stable
```

5. commit the collection bump

Later we can automate the promote step with a pull request opened from the node repo.

To assemble from published GitHub node releases instead of sibling local repos:

```powershell
python tools/assemble_collection.py --source github-release --statuses stable
```

This writes:

- `TCollection-vX.Y.Z.zip`
- `latest.json`
- `SHA256SUMS.txt`

## Artist flow target

At startup, TCollection should:

- bootstrap stable nodes
- register one `Nodes > TCollection` menu
- optionally check a remote update manifest
- notify artists when a newer collection version is available
- download the update for the next launch instead of replacing loaded binaries

The updater foundations are already scaffolded in `tcollection/updater.py`.

## Current status

This initial scaffold defines the collection contract and runtime foundation.
It now also includes:

- a node promotion helper from local sibling repos
- a local collection assembler for dev and QA packaging
- a GitHub-release collection assembler for CI publishing
- a GitHub release update check path for the future in-Nuke updater

The main remaining product work is now on top of that GitHub base:

- automating node-to-collection promotion even further
- implementing the in-Nuke download/apply update UX

## GitHub operating model

The GitHub side is now organized around one simple rule:

- each node keeps its own repository, CI, and releases
- `TCollection` only decides which released versions are exposed to artists

That gives you a clean day-to-day workflow:

1. update the node in its own repo
2. publish the node release
3. run `python tools/promote_node.py <NodeKey>` in `TCollection`
4. review the generated metadata and catalog changes
5. merge to `main`
6. tag `TCollection` when you want a new artist-facing package
