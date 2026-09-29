# CADUCEUS — Rapport Sprint 6

## Périmètre livré
Le Sprint 6 ajoute un étage d'arbitrage IA **après** le retrieval CAMCIS. Le moteur local reste la fondation ; les fournisseurs commerciaux ne sont appelés que lorsqu'un classement reste ambigu.

## Pipeline
1. Extraction / normalisation du document.
2. Confirmation immédiate des codes source valides dans CAMCIS.
3. Recherche hybride CAMCIS Top-5 pour les lignes sans code fiable.
4. Décision locale si le score et la marge sont suffisants.
5. Pour les seuls `A_REVOIR` pertinents : arbitrage IA fermé.
6. Validation stricte : le code sélectionné doit appartenir au Top-5 CAMCIS.
7. Sinon : abstention et conservation du classement prudent.

## Maîtrise des coûts
- 0 appel pour les lignes confirmées par CAMCIS.
- 0 appel pour les précédents experts quasi exacts.
- seuil minimal de retrieval avant appel IA ;
- plafond d'appels par dossier ;
- cache persistant ;
- benchmark commercial explicitement déclenché par l'utilisateur et limité par budget d'appels.

## Confidentialité
Les fournisseurs IA reçoivent uniquement : désignation normalisée, spécifications utiles, contexte d'usage minimal et candidats CAMCIS. Les prix, coordonnées, nom du client et nom du fichier ne sont pas transmis.

## Validation
- 33 tests automatisés passent.
- Régression SOCAAL : 170 lignes, 170 statuts `CONFIRME_SOURCE`, 0 appel IA lorsque l'assistance est désactivée/non nécessaire.
- Régression devis charpente : 22 lignes extraites.
- Garde-fou testé : un code inventé par un faux fournisseur est rejeté.

## À mesurer sur le poste projet
Les clés commerciales n'étant pas embarquées, les scores NVIDIA/OpenAI doivent être mesurés depuis l'onglet **Évaluation moteur** après configuration. Le benchmark est volontairement explicite pour éviter tout coût caché.
