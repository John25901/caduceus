# CADUCEUS V2.3 — Rapport Sprint 3

## Objectif

Étendre le pipeline de CADUCEUS à l'ingestion documentaire réelle sans modifier le moteur douanier : tout document est converti en `EquipmentItem[]` avant le mapping CAMCIS.

## Formats pris en charge

- Excel : `.xlsx`, `.xls`
- CSV / TXT
- Word : `.docx`
- PDF natif
- PDF scanné (OCR à la demande)
- Images : `.png`, `.jpg`, `.jpeg`, `.webp`, `.tif`, `.tiff`

## Architecture d'extraction

1. Détection du type de document.
2. Extraction native prioritaire (tableaux / texte).
3. OCR Tesseract uniquement si nécessaire.
4. Normalisation vers `EquipmentItem`.
5. Même moteur CAMCIS quel que soit le format d'origine.

Le moteur ne reçoit donc jamais directement un PDF ou une image.

## Sobriété / performances

Validation locale sur des documents réels du projet :

| Cas | Articles | Temps ingestion | OCR |
|---|---:|---:|---:|
| NETIC Excel | 423 | ~0,54 s | 0 page |
| SOCAAL — liste prévisionnelle PDF | 116 | ~2,33 s | 0 page |
| Proforma Egg Tray PDF | 1 | ~0,18 s | 0 page |
| Quotation charpente acier PDF | 22 | ~0,86 s | 0 page |
| Quotation carton ondulé 63 pages | 6 | ~0,31 s | 0 page |
| Raster de la proforma (image) | 1 | ~2,07 s | 1 page |
| PDF scanné de la proforma | 1 | ~7,46 s | 1 page |

Le PDF de 63 pages contient une liste commerciale au début puis des spécifications techniques détaillées. CADUCEUS détecte le marqueur de bascule et arrête l'analyse commerciale après la page 2 au lieu de parcourir les 63 pages comme des tableaux de marchandises.

## Sécurité métier

- L'OCR ne crée pas une quantité absente : si le scan permet de lire les prix mais pas la quantité, la quantité reste `null` et le document final passe en **À compléter**.
- Les paragraphes numérotés de paiement, garantie ou livraison ne sont pas transformés en équipements.
- L'extraction d'un PDF de spécifications n'est pas confondue avec la nomenclature commerciale lorsque la séparation est détectable.
- Les informations de provenance (page et méthode d'extraction) restent dans l'audit technique masqué, pas dans le tableau Direction.

## Dépendances

Les installations existantes V2.2 ne réinstallent pas Streamlit ni Sentence Transformers. Exécuter une seule fois :

```bat
update_to_v23.bat
```

Ce script vérifie d'abord si les cinq nouvelles bibliothèques sont déjà présentes et n'installe que `requirements-update-v2.3.txt` si nécessaire.

Tesseract est optionnel pour tous les documents natifs. Voir `OCR_SETUP.md`.

## Tests

17 tests automatisés passent sur le socle V2.3.
