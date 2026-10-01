# Guide utilisateur — CGS - Harmonisation Douanière

## 1. Lancer CGS - Harmonisation Douanière
Double-cliquer sur `run_caduceus.bat`. Le lancement courant ne réinstalle aucune dépendance.

## 2. Renseigner le dossier
Indiquer la référence, le secteur / activité et une description courte du projet ou du process. Cette description aide le contrôle sectoriel et, lorsqu'elle est activée, l'assistance IA sur les cas ambigus.

## 3. Importer le document
Formats admis : Excel, CSV, TXT, Word, PDF et images. CGS choisit automatiquement entre extraction native et OCR.

## 4. Vérifier l'extraction
Utiliser **Vérifier le document avant traitement** pour contrôler désignation, spécifications, quantité, unité, prix et origine. Une donnée insuffisamment fiable est laissée vide plutôt qu'inventée.

## 5. Harmoniser
Cliquer sur **Harmoniser la liste**.
- Un code source valide dans CAMCIS est confirmé immédiatement.
- Sinon, CGS recherche plusieurs candidats du référentiel douanier en interne.
- Le moteur local décide quand la preuve est suffisante.
- Si le cas reste ambigu et qu'un fournisseur IA est configuré, l'IA reçoit uniquement les candidats CAMCIS déjà trouvés. Elle choisit l'un d'eux ou s'abstient.

## 6. Assistance IA
L'option se trouve dans **Options avancées**. Le mode `AUTO` privilégie NVIDIA si configuré, puis OpenAI. Aucun appel n'est fait pour les lignes déjà confirmées.

Le système applique quatre garde-fous :
1. pas de prix, nom de client ou identifiant de dossier transmis au fournisseur ;
2. pas d'appel sur les lignes déjà fiables ;
3. budget maximum d'appels par dossier ;
4. tout code non présent dans la liste fermée de candidats est rejeté.

Pour configurer une clé : lancer une seule fois `configure_ai.bat`, puis redémarrer CGS.

## 7. Lire le résultat
La vue métier reste limitée aux informations utiles : désignation, position tarifaire, libellé, spécifications, quantité, unité, prix XAF, origine et observations. Les scores, candidats alternatifs et informations IA restent dans le diagnostic technique ou les feuilles d'audit masquées.

## 8. Exporter
Trois livrables sont disponibles : Excel harmonisé, rapport d'audit Word et rapport PDF. Les prix sont normalisés en XAF ; le prix total Excel est une formule `Quantité × Prix unitaire`.

## 9. Corriger et réimporter
Le classeur harmonisé peut être corrigé puis réimporté. Les contrôles sont rejoués. Une correction ne devient un précédent d'apprentissage que si l'utilisateur confirme qu'un expert douane a réellement validé la position.

## 10. Évaluer les modèles
L'onglet **Évaluation moteur** distingue :
- **Recherche CAMCIS** : capacité à placer le bon code dans les premières propositions ;
- **Arbitrage IA** : capacité à choisir le bon code quand il est déjà présent parmi les candidats mais mal classé.

Un test commercial est volontairement limité à quelques appels. Le tableau affiche la précision, les abstentions, la latence, les appels API et l'utilisation du cache. Le taux de sorties invalides doit rester à 0 % grâce au garde-fou.

## Codes couleur
- Jaune : harmonisation / modification proposée.
- Orange : vérification expert réellement utile.
- Bleu : écart de cohérence sectorielle.
- Rouge : donnée manquante ou classement non déterminé.

## OCR
Si l'interface indique que l'OCR est inactif, lancer `install_ocr_windows.bat` une seule fois. Les documents natifs restent utilisables sans OCR.
