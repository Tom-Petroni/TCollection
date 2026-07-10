## Summary

- explain the node or collection change

## Checks

- [ ] node release exists on GitHub if this PR promotes a node
- [ ] `python tools/sync_node_lock.py`
- [ ] `python tools/sync_manifest.py`
- [ ] `python tools/sync_node_catalog.py`
- [ ] `python tools/validate_collection.py`
- [ ] `python tools/assemble_collection.py --source github-release --statuses stable`

## Notes

- deployment risk
- nodes added or removed
- follow-up work if needed
