# Déploiement CADUCEUS V2.6 — GitHub + Streamlit Community Cloud

## Architecture déployée

Streamlit Community Cloud n'exécute qu'un entrypoint Streamlit. `streamlit_app.py`
lance donc FastAPI en processus local privé (`127.0.0.1:8000`), attend son endpoint
`/health`, puis charge l'interface `frontend/app.py`.

Le port FastAPI n'est pas exposé au public.

## CI/CD

- **CI :** `.github/workflows/ci.yml` exécute compilation + tests à chaque push/PR.
- **CD :** Streamlit Community Cloud surveille la branche GitHub déployée. Tout push
  sur `main` est automatiquement reflété dans l'application ; une modification de
  `requirements.txt` ou `packages.txt` déclenche une reconstruction complète.

## 1. Créer le dépôt GitHub

Créer un dépôt privé, par exemple `caduceus`, puis depuis ce dossier :

```bash
git init
git add .
git commit -m "CADUCEUS V2.6 deploy"
git branch -M main
git remote add origin https://github.com/VOTRE_COMPTE/caduceus.git
git push -u origin main
```

Ne jamais ajouter `.env` ni `.streamlit/secrets.toml`.

## 2. Déployer sur Streamlit Community Cloud

1. Connecter GitHub à Streamlit Community Cloud.
2. `Create app`.
3. Sélectionner le dépôt `caduceus`, branche `main`.
4. Entrypoint : `streamlit_app.py`.
5. `Advanced settings` : sélectionner **Python 3.11**.
6. Ajouter les secrets nécessaires (voir `.streamlit/secrets.toml.example`).
7. Déployer.

## 3. OCR

`packages.txt` installe automatiquement :

- `tesseract-ocr`
- `tesseract-ocr-fra`
- `tesseract-ocr-eng`

Aucune installation Windows n'est requise dans le cloud.

## 4. Persistance : limite importante de Community Cloud

Les fichiers générés pendant l'exécution ne sont pas garantis persistants sur
Community Cloud. Le référentiel CAMCIS et les cas historiques sont versionnés dans
GitHub, mais Qdrant local, métriques, audit, cache FX/LLM et corrections utilisateur
sont des données runtime.

Cette cible est donc adaptée à la **démonstration et validation de la version actuelle**.
Pour une mise en production multi-utilisateur, déplacer l'état durable vers une base
ou un stockage persistant externe, ou déployer le backend sur une infrastructure avec
volume persistant.

## 5. Recherche sémantique et ressources

Le premier cold start peut télécharger le modèle SentenceTransformer puis construire
l'index CAMCIS. Si Community Cloud atteint ses limites de mémoire, définir temporairement
`CADUCEUS_ENABLE_SEMANTIC="0"` dans les secrets permet de démarrer en mode lexical +
mémoire validée. Ce mode de secours ne doit pas être confondu avec la cible de production.

## 6. Cycle de mise à jour

```text
feature branch -> Pull Request -> GitHub Actions -> merge main -> Streamlit auto-update
```

Aucune copie manuelle de ZIP n'est nécessaire une fois le dépôt en place.
