# Nodes

The source repository keeps node registry metadata here.

Generated catalog metadata also lives here:

- `nodes/registry.json`: editorial source of truth for node entries
- `nodes/catalog.json`: generated GitHub-facing overview with repo and release links

Packaged TCollection builds are expected to include extracted node payloads under:

`nodes/<NodeKey>/publish`
