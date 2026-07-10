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
  current
```

## Comportement au demarrage

1. lire la version locale
2. lire soit un manifest distant leger, soit la derniere GitHub Release
3. comparer les versions
4. notifier si une nouvelle version existe

## Comportement de l'update

1. telecharger l'archive de la nouvelle collection
2. l'extraire dans `versions/<new-version>/`
3. marquer cette version comme prochaine version active
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
- points d'entree pour un check manuel ou au demarrage

Le telechargement et l'activation de la nouvelle version seront l'etape suivante.
