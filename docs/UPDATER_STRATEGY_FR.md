# Strategie de mise a jour artiste

## But

Permettre a un artiste de:

- voir qu'une nouvelle version existe
- lancer la preparation de mise a jour depuis Nuke
- relancer Nuke
- utiliser directement la nouvelle version

## Regle de robustesse

Les binaires deja charges par Nuke ne doivent pas etre remplaces en place.

La collection doit telecharger la nouvelle version dans un dossier versionne,
puis l'activer au prochain lancement.

## Layout recommande

```text
.nuke/TCollection/
  versions/
    0.1.0/
    0.2.0/
  current.json
  pending.json
```

Le package installe dans le plugin path Nuke reste un bootstrap stable.
Il lit `current.json` et `pending.json`, puis charge la vraie version active
depuis `versions/`.

## Comportement au demarrage

1. lire la version locale
2. promouvoir `pending.json` vers `current.json` si une update a ete preparee
2. lire soit un manifest distant leger, soit la derniere GitHub Release
3. comparer les versions
4. notifier si une nouvelle version existe

## Comportement de l'update

1. telecharger l'archive de la nouvelle collection
2. l'extraire dans `versions/<new-version>/`
3. marquer cette version dans `pending.json`
4. demander un redemarrage de Nuke

## Pourquoi cette approche

- pas de conflit avec des binaires deja charges
- rollback plus simple
- debugging plus simple
- installation deterministe

## Etat actuel

Le module `tcollection/updater.py` pose deja le contrat de base:

- lecture de la config update
- lecture d'un manifest distant JSON
- lecture optionnelle de la derniere GitHub Release du repo TCollection
- comparaison de versions
- telechargement de l'archive de release
- extraction dans `.nuke/TCollection/versions`
- preparation de la prochaine version active
- points d'entree pour un check manuel ou au demarrage

Le bootstrap stable est porte par:

- `init.py`
- `menu.py`
- `tcollection_bootstrap.py`

Le prochain gros sujet produit sera surtout l'onboarding artiste:

- ou placer le premier bootstrap
- comment documenter l'installation initiale
- comment nettoyer d'anciennes versions si besoin
