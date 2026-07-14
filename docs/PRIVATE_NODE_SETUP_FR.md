# TCollection: setup nodes prives

## Objectif

Garder:

- `TCollection` public
- les updates de la collection publiques
- les sources sensibles de certains nodes dans des repos GitHub prives

L'idee est simple:

- chaque node publie un zip runtime en GitHub Release
- `TCollection` telecharge cet asset au moment de l'assemblage
- `TCollection` n'a pas besoin d'acceder au code source du node

## Limite importante

Le `GITHUB_TOKEN` natif d'un workflow GitHub Actions est limite au repo dans
lequel tourne le workflow. Donc si `TCollection` doit lire les releases d'un
autre repo prive, il faut fournir un token explicite.

Dans ce projet, le secret recommande est:

- `TCOLLECTION_NODE_REPO_TOKEN`

## Setup recommande

### 1. Passer le repo node en prive

Tu peux garder par exemple:

- `Tom-Petroni/TCollection` en public
- `Tom-Petroni/TNoisePro` en prive

Le repo prive garde tout le code source, la CI et l'historique.

### 2. Continuer a publier une release runtime du node

Le repo node doit continuer de publier:

- un tag du style `v1.2.3`
- un asset zip du style `TNoisePro-v1.2.3.zip`

TCollection consomme uniquement cet asset.

### 3. Creer un fine-grained PAT GitHub

Le plus simple est un fine-grained personal access token avec acces seulement
aux repos prives de nodes a lire.

Permissions minimales recommandees:

- `Contents: Read`
- `Metadata: Read`

Si le repo appartient a une organisation, une approbation org peut etre
necessaire selon la policy GitHub.

### 4. Ajouter le secret dans le repo TCollection

Dans le repo GitHub `TCollection`:

1. `Settings`
2. `Secrets and variables`
3. `Actions`
4. `New repository secret`

Nom du secret:

- `TCOLLECTION_NODE_REPO_TOKEN`

## Utilisation locale

Pour tester localement un assemblage ou un audit avec des repos prives:

```powershell
$env:TCOLLECTION_NODE_REPO_TOKEN="ghp_xxx"
python tools/assemble_collection.py --source github-release --statuses stable
python tools/audit_node_sources.py --strict-enabled
```

Tu peux aussi utiliser l'alias suivant si besoin:

```powershell
$env:TCOLLECTION_GITHUB_TOKEN="ghp_xxx"
```

Mais le secret principal a garder partout reste `TCOLLECTION_NODE_REPO_TOKEN`.

## Utilisation CI

Les workflows collection sont deja prepares pour ce secret:

- `.github/workflows/audit-node-sources.yml`
- `.github/workflows/validate-collection.yml`
- `.github/workflows/publish-collection.yml`

Ils peuvent donc:

- auditer les nodes actifs
- telecharger des assets de release depuis des repos nodes prives
- assembler une release `TCollection` complete

## Promotion d'un node prive

Exemple de flux:

```powershell
python tools/promote_node.py TNoisePro --repo-path ..\TNoisePro
python tools/validate_collection.py
python tools/assemble_collection.py --source github-release --statuses stable
```

Ensuite:

- commit des metadata de collection
- tag de la version TCollection
- publication de la release collection

## Mode produit recommande

Pour une transition propre:

- `TCollection` reste public
- les nodes gratuits restent publics
- les nodes premium ou sensibles passent en prive
- les artistes gardent un seul point d'installation: `TCollection`
