# Migration V2.4 -> V2.5

1. Fermer CADUCEUS.
2. Copier le contenu du patch V2.5 à la racine de la V2.4 et accepter les remplacements.
3. Lancer **une seule fois** `update_to_v25.bat` afin d'activer Tesseract OCR sous Windows si nécessaire.
4. Lancer ensuite `run_caduceus.bat` normalement.

Ne pas relancer `requirements.txt` : la V2.5 n'ajoute aucune dépendance Python.
