# Migration V2.5 → V2.6

1. Fermer CADUCEUS.
2. Copier le contenu du patch V2.6 dans le dossier V2.5 et accepter les remplacements.
3. Ne pas réinstaller `requirements.txt`.
4. Lancer `run_caduceus.bat` : le moteur local fonctionne immédiatement.
5. Pour activer l'arbitrage commercial, lancer une seule fois `configure_ai.bat`, saisir la clé NVIDIA et/ou OpenAI, puis redémarrer CADUCEUS.

Les index CAMCIS, métriques, journaux et caches restent dans `%LOCALAPPDATA%\CADUCEUS` et sont conservés entre les versions.
