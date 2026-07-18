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
The node repository naming convention lives in [docs/NODE_REPO_STANDARD_FR.md](docs/NODE_REPO_STANDARD_FR.md).

## Install In Nuke

Current artist install target: one folder to extract, plus one line to add in
`.nuke/init.py`.

### 1. Find your `.nuke` folder

- Windows: `C:\Users\<YourUser>\.nuke`
- macOS: `/Users/<your-user>/.nuke`
- Linux: `/home/<your-user>/.nuke`

### 2. Download the latest TCollection release

Go to the GitHub releases page and download the latest
`TCollection-vX.Y.Z.zip` archive:

- [TCollection Releases](https://github.com/Tom-Petroni/TCollection/releases)

### 3. Extract it into `.nuke/TCollection`

Create this folder if it does not exist:

```text
.nuke/TCollection
```

Extract the ZIP contents directly inside that folder.

After extraction, this is what you should see inside `.nuke/TCollection`:

```text
TCollection/
  init.py
  menu.py
  tcollection_bootstrap.py
  VERSION
  config/
  nodes/
  tcollection/
```

### 4. Add TCollection to Nuke's plugin path

Open `.nuke/init.py`.

If the file does not exist yet, create it.

Add this line:

```python
import nuke
nuke.pluginAddPath("./TCollection")
```

If you already have an `init.py`, just append the line. Do not remove your
existing setup.

### 5. Launch Nuke

If the install is correct, you should see:

- a `Nodes > TCollection` menu
- the nodes `TBlur`, `TColorRamp`, `TMask`, and `TNoise`

### 6. Check that the managed install is working

In Nuke, open:

- `Nodes > TCollection > Show Install Status`

You can also test:

- `Nodes > TCollection > Check For Updates...`
- `Nodes > TCollection > Prepare Update For Next Launch...`

### Notes

- First install still requires one manual edit in `.nuke/init.py`
- Later updates are designed to download into `.nuke/TCollection/versions`
- The next launched version becomes active after restarting Nuke

## Repository layout

```text
TCollection/
  .devtools/            # dev-only scaffolding and workflow helpers, not shipped
  .github/workflows/    # collection validation and future packaging workflows
  config/               # collection settings + node repo mapping + lockfile
  docs/                 # source documentation, not shipped in the artist zip
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
python tools/audit_node_sources.py --strict-enabled
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

For QA, you can also mix published releases with one local archive override for a
node that is not released yet:

```powershell
python tools/assemble_collection.py --source github-release --statuses stable --archive-override TColorRamp=..\TColorRamp\dist\TColorRamp-v1.0.5.zip
```

This writes:

- `TCollection-vX.Y.Z.zip`
- `latest.json`
- `SHA256SUMS.txt`

The packaged artist zip only contains runtime files. Source-only
documentation and dev helpers stay out of the release payload, and placeholder
folders are skipped until they contain real artist-facing assets.

For dev-only helpers such as node scaffolding and worktree setup, see
[.devtools/README.md](.devtools/README.md).

## Artist flow target

At startup, TCollection should:

- bootstrap stable nodes
- register one `Nodes > TCollection` menu
- optionally check a remote update manifest
- notify artists when a newer collection version is available
- download the update for the next launch instead of replacing loaded binaries

The runtime now also supports a managed install flow:

- a stable bootstrap entrypoint stays in the artist plugin path
- downloaded versions are stored in `.nuke/TCollection/versions`
- a prepared update becomes active on the next Nuke launch

## Current status

This initial scaffold defines the collection contract and runtime foundation.
It now also includes:

- a node promotion helper from local sibling repos
- a local collection assembler for dev and QA packaging
- a GitHub-release collection assembler for CI publishing
- a GitHub release update check path for the future in-Nuke updater

The main remaining product work is now on top of that GitHub base:

- automating node-to-collection promotion even further
- polishing the in-Nuke update UX and installation onboarding

## GitHub operating model

The GitHub side is now organized around one simple rule:

- each node keeps its own repository, CI, and releases
- `TCollection` only decides which released versions are exposed to artists

### GitHub Actions model

- node repos:
  - `pull_request` and `push` on `main`: fast smoke CI only
  - `vX.Y.Z` tag or manual dispatch: full Windows/Linux build matrix for supported Nuke versions
  - optional manual sync of tracked `publish/.../bin` payloads when needed
- `TCollection`:
  - validate metadata and release assembly on every PR / `main` push
  - publish the artist-facing suite only from tagged releases or manual dispatch
  - audit active node GitHub repos and release assets on a schedule

This keeps daily iteration cheap while preserving one reliable release path for artists.

That gives you a clean day-to-day workflow:

1. update the node in its own repo
2. publish the node release
3. run `python tools/promote_node.py <NodeKey>` in `TCollection`
4. review the generated metadata and catalog changes
5. merge to `main`
6. tag `TCollection` when you want a new artist-facing package

There is also a dedicated GitHub audit workflow:

- `.github/workflows/audit-node-sources.yml`

It checks that active node repos, release tags, and expected assets still exist
on GitHub while keeping planned nodes visible without blocking the main
collection packaging flow.
