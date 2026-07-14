# TCollection: architecture

## Objectif

TCollection est le produit final vu par les artistes.

Les nodes restent libres d'evoluer dans leurs propres repos, mais la collection
centralise:

- le menu Nuke
- le bootstrap runtime
- les scripts et gizmos communs
- la politique de versions de suite
- le futur systeme de notification de mise a jour

## Separation des responsabilites

### Repo node

Le repo node sert a:

- coder le node
- compiler Windows et Linux
- publier une release `vX.Y.Z`
- rester public ou prive selon la strategie produit

### Repo TCollection

Le repo TCollection sert a:

- epingler quelles versions de nodes composent la suite
- publier une experience produit coherente
- embarquer les outils communs non lies a un seul node
- exposer un seul point d'installation

## Mode hybride recommande

Pour evoluer vers une offre partiellement fermee sans casser le workflow:

- garder `TCollection` public
- garder les nodes gratuits publics si tu veux continuer a te faire connaitre
- passer les nodes premium ou sensibles en repos prives
- publier seulement leurs zips runtime via GitHub Releases

Dans ce modele:

- la source du node prive reste invisible
- `TCollection` continue d'assembler la suite depuis des releases versionnees
- les artistes ne voient toujours qu'une seule release `TCollection`

La CI de `TCollection` peut consommer des releases de nodes prives via le secret
`TCOLLECTION_NODE_REPO_TOKEN`.

## Flux de mise a jour d'un node

Exemple avec `TNoise`:

1. vous travaillez dans `TNoise`
2. la CI de `TNoise` compile les versions Nuke supportees
3. vous publiez `TNoise v2.1.0`
4. vous lancez `python tools/promote_node.py TNoise`
5. vous regenerez ou validez les fichiers derives
6. vous assemblez un package local si besoin
7. vous publiez `TCollection v0.2.0`

Le point important est que l'artiste ne consomme pas directement la release
`TNoise`, mais la release validee de `TCollection`.

## Ce que la collection doit rester

- simple a installer
- simple a maintenir
- robuste aux rollbacks
- claire a versionner

## Ce que la collection ne doit pas faire

- remplacer des DLL ou SO pendant que Nuke est ouvert
- devenir un mega repo source de tous les nodes
- demander aux artistes de suivre plusieurs repos
