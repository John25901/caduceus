# CHANGELOG V2.6 — Sprint 6 : arbitrage IA contrôlé

## Objectif
Ajouter une assistance IA utile sur les seuls cas tarifaires ambigus, sans autoriser un modèle génératif à inventer une position douanière.

## Nouveautés
- Arbitrage fermé : l'IA choisit uniquement parmi les candidats CAMCIS Top-5 déjà récupérés, ou s'abstient.
- Toute réponse proposant un code absent de la liste de candidats est rejetée par un garde-fou logiciel.
- Aucune donnée financière, nom de client ou identifiant de dossier n'est envoyé au fournisseur IA.
- Routage économique : aucun appel IA pour les codes déjà confirmés par la source ou par la mémoire experte.
- Budget d'appels par dossier configurable, par défaut 25 appels maximum.
- Cache persistant des décisions IA pour éviter de payer deux fois le même arbitrage inchangé.
- Intégration optionnelle NVIDIA API Catalog (Kimi) et OpenAI, sans nouvelle dépendance Python.
- Nouveau statut métier `PROPOSITION_ARBITREE` : harmonisation assistée, toujours soumise à validation experte avant dépôt.
- Model Lab étendu : couverture Top-5, précision de l'arbitrage, précision bout-en-bout, abstentions, sorties invalides, latence, tokens et appels API.
- Configuration simplifiée via `configure_ai.bat`.

## Sécurité
Le LLM n'a jamais la possibilité d'écrire librement un code SH dans le résultat. Le code final doit exister dans CAMCIS et appartenir aux candidats fournis au modèle.

## Dépendances
Aucune nouvelle dépendance. Ne relancez pas `requirements.txt` pour passer de V2.5 à V2.6.
