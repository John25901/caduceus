# CADUCEUS V2.4 — Sprint 4 : fiabilisation métier

## Corrections critiques
- Correction du parseur PDF : un tableau douanier à 8 colonnes n'est plus interprété comme une table `Prix/Qté/Montant`.
- Correction de la déduplication PDF : des lignes différentes ayant le même montant ne sont plus fusionnées.
- Conservation des unités `set`, `pcs`, `m²`, `t`, etc. lorsqu'elles existent dans le document source.
- Préférence automatique des colonnes de prix FCFA/XAF lorsqu'un Excel contient simultanément USD et FCFA.
- Confirmation directe d'une position source lorsqu'elle existe dans CAMCIS : pas de revue tarifaire artificielle de toutes les lignes.

## Monnaie et contrôle financier
- Devise professionnelle de restitution : XAF.
- Aucun taux de change n'est inventé.
- Pour USD/EUR, l'utilisateur fournit le taux applicable au dossier.
- Si seule la valeur totale est fournie, le prix unitaire peut être dérivé de façon déterministe.
- Dans le classeur final, `Prix total (XAF)` est une formule `Quantité × Prix unitaire`.
- Détection des incohérences entre total source et quantité × prix unitaire.

## Cohérence sectorielle
- Première version indépendante et explicable du moteur sectoriel.
- Statuts : `COHERENT`, `JUSTIFIABLE`, `A_EXAMINER`, `NON_EVALUEE`.
- Aucun article n'est déclaré non éligible automatiquement sur une simple faible similarité.
- Profils actuels : papier/carton, solaire PV, BTP, hôtellerie/loisirs, agro-industrie, énergie.

## Restitution
- Aucun sous-total automatique inventé.
- Noms de fichiers liés au fichier source.
- Excel harmonisé + synthèse d'audit visible + audit technique masqué.
- Rapport d'audit Word.
- Rapport d'audit PDF.
- Suppression du chinois dans la restitution professionnelle lorsqu'une traduction fiable n'est pas disponible ; le texte source reste conservé dans l'audit.

## Boucle d'amélioration
- Le classeur harmonisé peut être corrigé puis réimporté pour relancer tous les contrôles.
- Les corrections ne sont jamais mémorisées silencieusement.
- Une option explicite permet d'ajouter des positions réellement validées par un expert douane à la mémoire de précédents persistante.

## Dépendances
Aucune nouvelle dépendance par rapport à V2.3.
