from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

API_BASE = os.getenv("CADUCEUS_API_BASE", "http://127.0.0.1:8000").rstrip("/")
INTERNAL_TOP_K = 5  # Paramètre moteur, volontairement masqué à l'utilisateur métier.

st.set_page_config(page_title="CGS - Harmonisation Douanière", layout="wide")

# Charte visuelle CREATIV GROUP SARL : gris + rouge bordeaux.
st.markdown(
    """
<style>
:root {
  --cgs-bordeaux: #982040;
  --cgs-bordeaux-dark: #74172f;
  --cgs-bordeaux-soft: #f4e8ec;
  --cgs-charcoal: #2f3136;
  --cgs-gray: #6d7076;
  --cgs-gray-light: #e7e7e9;
  --cgs-surface: #f5f5f6;
  --cgs-white: #ffffff;
}

.stApp { background: var(--cgs-surface); color: #25272b; }
[data-testid="stSidebar"] { background: var(--cgs-charcoal); border-right: 4px solid var(--cgs-bordeaux); }
[data-testid="stSidebar"] * { color: #f4f4f4; }
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea,
[data-testid="stSidebar"] [data-baseweb="select"] * { color: #f4f4f4 !important; }
[data-testid="stSidebar"] hr { border-color: #55585e; }

.cgs-brand-header {
  background: linear-gradient(120deg, #ffffff 0%, #f6f6f7 72%, #f4e8ec 100%);
  border-left: 7px solid var(--cgs-bordeaux);
  border-bottom: 1px solid #d8d8db;
  border-radius: 8px;
  padding: 1.15rem 1.35rem 1.05rem 1.35rem;
  margin: 0 0 1.1rem 0;
  box-shadow: 0 2px 8px rgba(25, 25, 28, .05);
}
.cgs-brand-kicker { color: var(--cgs-bordeaux); font-size: .78rem; font-weight: 800; letter-spacing: .09em; text-transform: uppercase; margin-bottom: .2rem; }
.cgs-brand-title { color: #24262a; font-size: 2.15rem; font-weight: 800; line-height: 1.12; margin: 0; }
.cgs-brand-subtitle { color: #62656b; font-size: .98rem; margin-top: .45rem; max-width: 1050px; }
.cgs-sidebar-brand { border-bottom: 1px solid #5a5c61; padding: .15rem 0 1rem 0; margin-bottom: .8rem; }
.cgs-sidebar-brand strong { color: #ffffff !important; font-size: 1.05rem; }
.cgs-sidebar-brand span { color: #d8d8db !important; font-size: .78rem; }

.stButton > button, .stDownloadButton > button {
  border-radius: 6px;
  border: 1px solid var(--cgs-bordeaux) !important;
  font-weight: 700;
}
.stButton > button[kind="primary"], .stDownloadButton > button {
  background: var(--cgs-bordeaux) !important;
  color: white !important;
}
.stButton > button[kind="primary"]:hover, .stDownloadButton > button:hover {
  background: var(--cgs-bordeaux-dark) !important;
  border-color: var(--cgs-bordeaux-dark) !important;
}
[data-baseweb="tab-list"] { gap: .2rem; border-bottom: 1px solid #d7d7da; }
button[data-baseweb="tab"] { color: #4b4d52 !important; font-weight: 700; }
button[data-baseweb="tab"][aria-selected="true"] { color: var(--cgs-bordeaux) !important; border-bottom-color: var(--cgs-bordeaux) !important; }
[data-testid="stMetric"] { background: #ffffff; border-top: 3px solid var(--cgs-bordeaux); padding: .75rem; border-radius: 6px; }
[data-testid="stDataFrame"] { border: 1px solid #d4d4d7; border-radius: 6px; overflow: hidden; }
div[data-testid="stAlert"] { border-radius: 6px; }
hr { border-color: #d9d9dc; }
</style>
<div class="cgs-brand-header">
  <div class="cgs-brand-kicker">CREATIV GROUP SARL</div>
  <div class="cgs-brand-title">CGS - Harmonisation Douanière</div>
  <div class="cgs-brand-subtitle">Plateforme propriétaire d'ingénierie douanière : ingestion documentaire, harmonisation tarifaire, contrôle de cohérence et rapports professionnels.</div>
</div>
    """,
    unsafe_allow_html=True,
)


def api_get(path: str, timeout: int = 30):
    return requests.get(f"{API_BASE}{path}", timeout=timeout)


def api_post(path: str, **kwargs):
    return requests.post(f"{API_BASE}{path}", **kwargs)


def _business_observation(a: dict) -> str:
    item = a.get("item") or {}
    notes = []
    status = a.get("statut_tarifaire")
    sector = a.get("pertinence_sectorielle")
    if not a.get("code_sh_propose") or status == "NON_CLASSE":
        notes.append("Classement non déterminé : expertise douanière requise.")
    elif status == "A_REVOIR":
        notes.append("Position tarifaire à confirmer par l'expert.")
    elif status == "PROPOSITION_ARBITREE":
        notes.append("Position proposée après arbitrage IA contrôlé parmi les candidats du référentiel douanier ; validation experte avant dépôt.")
    if sector == "A_EXAMINER":
        notes.append(a.get("commentaire_sectoriel") or "Cohérence sectorielle à examiner.")
    elif sector == "JUSTIFIABLE":
        notes.append(a.get("commentaire_sectoriel") or "Équipement support à justifier dans le process.")
    if item.get("note_prix") and item.get("statut_prix") not in {None, "OK", "UNITE_DERIVEE", "TOTAL_DERIVE"}:
        notes.append(item.get("note_prix"))
    if (item.get("raw_fields") or {}).get("foreign_text_suppressed"):
        notes.append("Texte non francophone masqué dans la restitution professionnelle ; traduction/validation recommandée.")
    return " ".join(dict.fromkeys(x for x in notes if x))


def _business_table(payload: dict) -> pd.DataFrame:
    rows = []
    for idx, a in enumerate(payload.get("resultats", []), start=1):
        item = a.get("item") or {}
        rows.append({
            "N° d'ordre": idx,
            "Désignation": item.get("designation_source"),
            "Position tarifaire": a.get("code_sh_propose"),
            "Libellé douanier": a.get("libelle_propose"),
            "Spécifications": item.get("specifications"),
            "Quantité": item.get("quantite"),
            "Unité": item.get("unite"),
            "Prix unitaire (XAF)": item.get("prix_unitaire_xaf"),
            "Prix total (XAF)": item.get("prix_total_xaf"),
            "Origine": item.get("origine"),
            "Observations": _business_observation(a),
        })
    return pd.DataFrame(rows)


def _technical_table(payload: dict) -> pd.DataFrame:
    rows = []
    for idx, a in enumerate(payload.get("resultats", []), start=1):
        cands = a.get("candidats") or []
        rows.append({
            "N°": idx,
            "Désignation": (a.get("item") or {}).get("designation_source"),
            "Score retrieval": a.get("score_retrieval"),
            "Statut technique": a.get("statut_tarifaire"),
            "Top candidats": " | ".join(
                f"{c.get('code_sh')} ({float(c.get('combined_score') or 0):.3f})" for c in cands[:5]
            ),
            "Motif technique": a.get("motif_decision"),
            "Arbitrage IA": a.get("arbitrage_ia_statut"),
            "Fournisseur IA": a.get("arbitrage_ia_provider"),
            "Modèle IA": a.get("arbitrage_ia_model"),
            "Confiance IA": a.get("arbitrage_ia_confidence"),
            "Commentaire IA": a.get("arbitrage_ia_commentaire"),
        })
    return pd.DataFrame(rows)


with st.sidebar:
    st.subheader("Dossier")
    ref_client = st.text_input("Référence dossier", "DOSSIER-CREATIV-001")
    secteur = st.text_input("Secteur / activité", "")
    description_projet = st.text_area(
        "Description du projet / process",
        "",
        help="Décrivez brièvement l'activité, les produits fabriqués et les principales étapes du process. Ce champ alimentera le moteur sectoriel.",
    )
    taux_change_xaf = 0.0
    with st.expander("Options avancées", expanded=False):
        st.caption("Le taux de change est récupéré automatiquement. Renseignez un taux manuel uniquement si le dossier possède un taux officiel à imposer.")
        taux_change_xaf = st.number_input(
            "Taux officiel du dossier vers XAF (optionnel)",
            min_value=0.0, value=0.0, step=0.01,
            help="Cette valeur remplace le taux automatique uniquement pour un document à devise étrangère unique.",
        )
        assistance_ia = st.checkbox(
            "Assistance IA sur les cas tarifaires ambigus", value=True,
            help="CGS n'envoie à l'IA que la désignation, les spécifications utiles et une liste fermée de candidats du référentiel douanier. L'IA ne peut pas créer un nouveau code.",
        )
        llm_provider = st.selectbox(
            "Fournisseur d'arbitrage", ["AUTO", "NVIDIA", "OPENAI"], index=0,
            help="AUTO utilise NVIDIA si configuré, puis OpenAI. Aucun appel n'est effectué pour les lignes déjà confirmées par le référentiel douanier ou la mémoire experte.",
        )

    st.divider()
    st.subheader("État du système")
    try:
        r = api_get("/health", timeout=5)
        if r.ok:
            h = r.json()
            if h["status"] == "ok":
                st.success(f"Prêt — {h['camcis']['records']} positions de référence")
            else:
                st.warning("Prêt en mode dégradé")
            st.caption(f"Index référentiel : {h['semantic_index']['status']}")
            ocr = (h.get("ingestion") or {}).get("ocr") or {}
            if ocr.get("available"):
                st.caption(f"OCR : disponible ({ocr.get('engine', 'Tesseract')})")
            else:
                st.caption("OCR images/scans : moteur à activer — lancez une fois install_ocr_windows.bat")
            llm = h.get("llm_arbitration") or {}
            configured_ai = [p for p in (llm.get("providers") or []) if p.get("configured")]
            if configured_ai:
                labels = ", ".join(f"{p.get('provider')} / {p.get('model')}" for p in configured_ai)
                st.caption(f"Arbitrage IA : disponible — {labels}")
            else:
                st.caption("Arbitrage IA : non configuré — moteur local reste opérationnel")
            st.caption("Docker : non requis")
        else:
            st.error("API indisponible")
    except Exception:
        st.warning("API en cours de démarrage…")

mapping_tab, guide_tab, metrics_tab, eval_tab = st.tabs(
    ["Traitement d'un dossier", "Guide utilisateur", "Santé & métriques", "Évaluation moteur"]
)

with mapping_tab:
    st.subheader("1. Importer la liste du client")
    uploaded = st.file_uploader(
        "Document client",
        type=["xlsx", "xls", "csv", "txt", "docx", "pdf", "png", "jpg", "jpeg", "webp", "tif", "tiff"],
        help=(
            "Excel/CSV : détection automatique des en-têtes. Word/PDF : extraction native des tableaux et du texte. "
            "Images et pages PDF scannées : OCR Tesseract à la demande."
        ),
    )

    if uploaded is not None:
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Vérifier le document avant traitement"):
                try:
                    r = api_post(
                        "/api/v2/preview-bordereau",
                        files={"file": (uploaded.name, uploaded.getvalue())},
                        timeout=180,
                    )
                    if r.ok:
                        p = r.json()
                        st.session_state["preview_v22"] = p
                    else:
                        st.error(r.text)
                except Exception as exc:
                    st.error(str(exc))
        with c2:
            if st.button("Harmoniser la liste", type="primary"):
                with st.spinner("Analyse de la liste et rapprochement avec le référentiel douanier…"):
                    try:
                        r = api_post(
                            "/api/v2/process-bordereau",
                            files={"file": (uploaded.name, uploaded.getvalue())},
                            data={
                                "secteur": secteur,
                                "description_projet": description_projet,
                                "reference_prospect": ref_client,
                                "top_k": str(INTERNAL_TOP_K),
                                "taux_change_xaf": str(taux_change_xaf),
                                "assistance_ia": str(bool(assistance_ia)).lower(),
                                "llm_provider": llm_provider,
                            },
                            timeout=900,
                        )
                        if not r.ok:
                            st.error(r.text)
                        else:
                            st.session_state["v22_result"] = r.json()
                    except Exception as exc:
                        st.error(str(exc))

    if "preview_v22" in st.session_state:
        p = st.session_state["preview_v22"]
        with st.expander("Aperçu de l'extraction", expanded=True):
            source_type = p.get("source_type") or "DOCUMENT"
            method = p.get("extraction_method") or "détection automatique"
            source_sheet = p.get("source_sheet")
            details = f" — feuille « {source_sheet} »" if source_sheet else ""
            ocr_note = f" — {p.get('pages_ocr')} page(s) OCR" if p.get("pages_ocr") else ""
            st.info(f"{p['items_count']} articles détectés — {source_type} / {method}{details}{ocr_note}.")
            if p.get("warnings"):
                for w in p["warnings"]:
                    st.warning(w)
            preview_df = pd.DataFrame(p.get("preview") or [])
            display_cols = [
                c for c in ["designation_source", "specifications", "quantite", "unite", "prix_unitaire", "prix_total", "origine"]
                if c in preview_df.columns
            ]
            if display_cols:
                preview_df = preview_df[display_cols].rename(columns={
                    "designation_source": "Désignation",
                    "specifications": "Spécifications",
                    "quantite": "Quantité",
                    "unite": "Unité",
                    "prix_unitaire": "Prix unitaire",
                    "prix_total": "Prix total",
                    "origine": "Origine",
                })
                st.dataframe(preview_df, use_container_width=True, hide_index=True)

    if "v22_result" in st.session_state:
        payload = st.session_state["v22_result"]
        resultats = payload.get("resultats") or []
        business_df = _business_table(payload)
        n_total = len(resultats)
        n_confirmed = sum(1 for a in resultats if a.get("statut_tarifaire") in {"CONFIRME_SOURCE", "CONFIRME_MEMOIRE"})
        n_review = sum(1 for a in resultats if a.get("statut_tarifaire") == "A_REVOIR")
        n_unclassified = sum(1 for a in resultats if a.get("statut_tarifaire") == "NON_CLASSE")
        n_proposed = sum(1 for a in resultats if a.get("statut_tarifaire") == "PROPOSITION")
        n_arbitrated = sum(1 for a in resultats if a.get("statut_tarifaire") == "PROPOSITION_ARBITREE")
        n_sector_review = sum(1 for a in resultats if a.get("pertinence_sectorielle") == "A_EXAMINER")

        st.subheader("2. Liste harmonisée")
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("Articles", n_total)
        k2.metric("Codes confirmés", n_confirmed)
        k3.metric("Arbitrages IA", n_arbitrated)
        k4.metric("Propositions locales", n_proposed)
        k5.metric("Revue tarifaire", n_review + n_unclassified)
        k6.metric("Revue sectorielle", n_sector_review)
        profile = payload.get("project_profile") or {}
        if profile.get("label"):
            st.caption(f"Profil projet : {profile.get('label')} — confiance de détection {float(profile.get('confidence') or 0):.0%} ({profile.get('source')}).")
        fx = payload.get("exchange_rates") or {}
        if fx:
            fx_parts = []
            for curr, meta in fx.items():
                rate = meta.get("xaf_per_unit")
                if rate:
                    fx_parts.append(f"1 {curr} = {float(rate):,.3f} XAF ({meta.get('rate_date') or 'parité/référence courante'})")
            if fx_parts:
                st.caption("Conversion automatique : " + " ; ".join(fx_parts))
        llm_summary = payload.get("llm_arbitration") or {}
        if llm_summary.get("enabled"):
            st.caption(
                f"Arbitrage IA contrôlé : {llm_summary.get('selected', 0)} sélection(s), "
                f"{llm_summary.get('abstained', 0)} abstention(s), {llm_summary.get('api_calls', 0)} appel(s) API, "
                f"{llm_summary.get('cache_hits', 0)} réponse(s) réutilisée(s) depuis le cache."
            )

        st.dataframe(
            business_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Position tarifaire": st.column_config.TextColumn(width="medium"),
                "Libellé douanier": st.column_config.TextColumn(width="large"),
                "Désignation": st.column_config.TextColumn(width="medium"),
                "Observations": st.column_config.TextColumn(width="large"),
            },
        )

        st.subheader("3. Exports professionnels")
        st.caption(
            "La liste Excel est en XAF, sans sous-totaux inventés, et le prix total est une formule Quantité × Prix unitaire. "
            "Le rapport d'audit est disponible en Word et PDF pour le superviseur."
        )
        export_body = {
            "payload": payload,
            "reference_dossier": ref_client,
            "secteur": secteur,
            "description_projet": description_projet,
        }
        source_stem = (payload.get("source_filename") or ref_client).rsplit(".", 1)[0]
        safe_stem = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in source_stem).strip("_") or "DOSSIER"
        try:
            colx, colw, colp = st.columns(3)
            with colx:
                export_response = api_post("/api/v2/export/excel", json=export_body, timeout=120)
                if export_response.ok:
                    st.download_button(
                        "Liste harmonisée Excel", data=export_response.content,
                        file_name=f"{safe_stem}_harmonise_CGS.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary",
                    )
            with colw:
                wr = api_post("/api/v2/export/audit/docx", json=export_body, timeout=120)
                if wr.ok:
                    st.download_button(
                        "Rapport d'audit Word", data=wr.content, file_name=f"{safe_stem}_rapport_audit_CGS.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
            with colp:
                pr = api_post("/api/v2/export/audit/pdf", json=export_body, timeout=120)
                if pr.ok:
                    st.download_button(
                        "Rapport d'audit PDF", data=pr.content, file_name=f"{safe_stem}_rapport_audit_CGS.pdf",
                        mime="application/pdf",
                    )
        except Exception as exc:
            st.error(f"Export indisponible : {exc}")

        with st.expander("Cycle d'amélioration / réimport", expanded=False):
            st.write(
                "Ouvrez la liste harmonisée Excel, corrigez-la puis réimportez-la dans le traitement standard pour relancer tous les contrôles. "
                "Si un expert douane a réellement validé les positions, vous pouvez en plus les enregistrer explicitement comme précédents humains."
            )
            reviewed = st.file_uploader(
                "Fichier harmonisé révisé par l'expert",
                type=["xlsx", "xls", "csv"],
                key="reviewed_harmonized_file",
            )
            expert_ok = st.checkbox(
                "Je confirme que les positions tarifaires de ce fichier ont été validées par un expert douane",
                key="expert_confirmation",
            )
            if st.button("Ajouter aux précédents validés", disabled=(reviewed is None or not expert_ok)):
                try:
                    rr = api_post(
                        "/api/v2/feedback/import-validated",
                        files={"file": (reviewed.name, reviewed.getvalue())},
                        data={"expert_confirmation": "true"},
                        timeout=180,
                    )
                    if rr.ok:
                        info = rr.json()
                        st.success(f"{info.get('added_cases', 0)} nouveau(x) précédent(s) validé(s) enregistré(s).")
                        if info.get("invalid_codes"):
                            st.warning("Certaines positions ne sont pas présentes dans le référentiel douanier et n'ont pas été mémorisées.")
                    else:
                        st.error(rr.text)
                except Exception as exc:
                    st.error(str(exc))

        with st.expander("Diagnostic technique — équipe projet uniquement", expanded=False):
            st.caption(
                "Ces informations servent à l'évaluation du moteur et à la validation interne. Elles ne figurent pas dans la restitution destinée à la Direction."
            )
            st.dataframe(_technical_table(payload), use_container_width=True, hide_index=True)
            perf = payload.get("performance") or {}
            st.write({
                "mode_moteur": payload.get("search_mode"),
                "temps_total_s": round(float(perf.get("total_ms") or 0) / 1000, 3),
                "type_document": perf.get("source_type"),
                "méthode_extraction": perf.get("extraction_method"),
                "pages_ocr": perf.get("pages_ocr"),
                "recherche_moyenne_ms": perf.get("avg_search_ms"),
                "mémoire_delta_mb": perf.get("rss_delta_mb"),
            })

with guide_tab:
    st.subheader("Guide utilisateur — traitement standard")
    st.markdown(
        """
**Étape 1 — Renseigner le dossier**  
Indiquez une référence, le secteur d'activité et, si disponible, une courte description du process industriel.

**Étape 2 — Importer le document client**  
Chargez un fichier Excel, CSV, TXT, Word, PDF ou une image. CGS privilégie toujours l'extraction native. L'OCR n'est utilisé que pour les images ou les pages PDF sans texte exploitable.

**Étape 3 — Vérifier l'extraction**  
Utilisez **Vérifier le document avant traitement** pour contrôler rapidement que les désignations, quantités, unités, prix et origines ont été correctement reconnus. Pour un PDF volumineux, CGS privilégie la partie commerciale et évite de parcourir inutilement les annexes techniques détaillées lorsqu'un séparateur clair est détecté.

**Étape 4 — Harmoniser**  
Cliquez sur **Harmoniser la liste**. Si le document contient déjà une position tarifaire valide dans le référentiel douanier, CGS la confirme et applique le libellé officiel au lieu de demander une revue inutile. Pour les lignes sans code, plusieurs candidats sont recherchés en interne. Si le classement reste ambigu et qu’un fournisseur IA est configuré, CGS lui transmet uniquement une liste fermée de candidats du référentiel douanier : il doit en choisir un ou s’abstenir, sans pouvoir inventer une position.

**Étape 5 — Lire les alertes**  
La liste principale ne montre que les informations utiles au dossier. Les cas à vérifier ou à compléter apparaissent dans la colonne **Observations** et dans le classeur Excel par codes couleur.

**Étape 6 — Exporter**  
Téléchargez la liste harmonisée Excel et, si nécessaire, le rapport d'audit Word ou PDF. Les prix professionnels sont restitués en XAF. CGS récupère automatiquement un taux de référence quand la devise est étrangère et conserve sa source/date dans l'audit. Un taux officiel de dossier peut toujours être imposé dans les options avancées. Le prix total Excel est calculé par formule ; aucun sous-total n'est inventé par CGS.

**Étape 7 — Améliorer / réimporter**  
Après revue humaine, vous pouvez modifier le classeur harmonisé et le réimporter. CGS recommence les contrôles sur la version corrigée et signale les nouveaux écarts éventuels.

**Important** : CGS propose et documente le classement. La validation humaine reste requise avant dépôt officiel auprès de l'administration.
        """
    )
    st.info(
        "Le réglage « nombre de candidats du référentiel » a été retiré de l'interface métier : il s'agit d'un paramètre interne du moteur, pas d'une décision utilisateur."
    )
    st.caption(
        "OCR : les images et PDF scannés utilisent Tesseract. Sous Windows, le patch fournit install_ocr_windows.bat pour activer automatiquement le moteur une seule fois ; les formats natifs restent utilisables en toutes circonstances."
    )

with metrics_tab:
    st.subheader("Santé & métriques")
    st.caption("Lecture automatique de l'état du moteur. Aucun rafraîchissement manuel n'est requis au démarrage.")
    try:
        h = api_get("/health", timeout=10).json()
        idx = h["semantic_index"]
        m = h["metrics"]
        a, b, c, d = st.columns(4)
        a.metric("Positions de référence", h["camcis"]["records"])
        b.metric("Cas validés", h["validated_memory"]["cases"])
        c.metric("Index sémantique", idx["status"])
        d.metric("Démarrage API", f"{(m.get('last_startup_ms') or 0)/1000:.2f} s")
        st.caption("Les métriques détaillées ci-dessous servent à l'équipe projet ; elles ne figurent pas dans les livrables Direction.")
        runtime = api_get("/api/v2/metrics/runtime?limit=50", timeout=10).json().get("events", [])
        if runtime:
            rdf = pd.DataFrame(runtime)
            cols = [c for c in ["created_at", "event_type", "duration_ms", "rss_delta_mb"] if c in rdf.columns]
            st.dataframe(rdf[cols], use_container_width=True, hide_index=True)
        else:
            st.info("Aucune mesure d'exécution enregistrée pour l'instant.")
    except Exception:
        st.info("Les métriques seront affichées automatiquement dès que l'API sera prête.")

with eval_tab:
    st.subheader("Évaluation du moteur")
    st.write("Cette page mesure la capacité du moteur à retrouver le bon code du référentiel sur des dossiers déjà validés. Plus les pourcentages sont élevés, meilleur est le moteur ; plus le temps par recherche est faible, plus il est rapide.")
    st.markdown("**Comment lire les indicateurs :** Top-1 = le bon code arrive en première position ; Top-3 = il apparaît parmi les 3 premiers ; Top-5 = parmi les 5 premiers. Le MRR mesure la qualité du classement global (1 = idéal).")

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Mesurer la recherche lexicale", use_container_width=True):
            with st.spinner("Évaluation en cours…"):
                r = api_post("/api/v2/evaluation/run-lexical-baseline?max_cases=200", timeout=900)
                if r.ok: st.success("Mesure enregistrée.")
                else: st.error(r.text)
    models = [
        ("MiniLM multilingue", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
        ("E5 multilingue", "intfloat/multilingual-e5-small"),
    ]
    for col, (label, model) in zip((c2, c3), models):
        with col:
            if st.button(f"Tester {label}", use_container_width=True):
                with st.spinner(f"Évaluation {label} — peut prendre quelques minutes…"):
                    r = api_post(f"/api/v2/evaluation/run-local-model?model_name={model}&max_cases=200", timeout=3600)
                    if r.ok: st.success("Mesure enregistrée.")
                    else: st.error(r.text)

    try:
        results = api_get("/api/v2/evaluation/results?limit=100", timeout=10).json().get("results", [])
        if not results:
            st.info("Aucune évaluation enregistrée pour l'instant.")
        else:
            df = pd.DataFrame(results).copy()
            names = {
                "LEXICAL": "Recherche lexicale",
                "SEMANTIC": "Recherche sémantique",
                "HYBRID_RRF": "Recherche hybride",
            }
            df["Méthode"] = df["engine_type"].map(names).fillna(df["engine_type"])
            df["Modèle"] = df["model_name"].fillna("Sans modèle IA")
            df["Top-1"] = (df["top1_accuracy"].fillna(0) * 100).round(1).astype(str) + " %"
            df["Top-3"] = (df["top3_recall"].fillna(0) * 100).round(1).astype(str) + " %"
            df["Top-5"] = (df["top5_recall"].fillna(0) * 100).round(1).astype(str) + " %"
            df["MRR"] = df["mrr"].round(3)
            df["Temps moyen (ms)"] = df["avg_query_ms"].round(1)
            display = df[["Méthode", "Modèle", "cases", "Top-1", "Top-3", "Top-5", "MRR", "Temps moyen (ms)"]].rename(columns={"cases":"Cas testés"})
            st.dataframe(display, use_container_width=True, hide_index=True)
            st.caption("Le laboratoire n'adopte aucun modèle automatiquement : les résultats servent à choisir le meilleur compromis précision / latence / mémoire.")
            with st.expander("Détails techniques", expanded=False):
                raw_cols = [c for c in ["created_at","engine_type","model_name","top1_accuracy","top3_recall","top5_recall","mrr","avg_query_ms","p95_query_ms","corpus_build_seconds","rss_delta_mb"] if c in df.columns]
                st.dataframe(df[raw_cols], use_container_width=True, hide_index=True)
    except Exception:
        st.info("Les résultats d'évaluation apparaîtront ici dès que l'API sera disponible.")

    st.divider()
    st.subheader("Arbitrage IA des cas ambigus")
    st.write(
        "Cette mesure intervient après la recherche dans le référentiel douanier. Le fournisseur reçoit uniquement les candidats déjà trouvés par CGS. "
        "Il doit choisir l'un d'eux ou s'abstenir. Le test ne dépense des appels que sur des cas où le bon code est déjà présent dans le Top-5 mais n'est pas classé premier."
    )
    try:
        provider_info = api_get("/api/v2/evaluation/llm-providers", timeout=10).json()
        providers = provider_info.get("providers") or []
        configured = [p for p in providers if p.get("configured")]
        if not configured:
            st.info("Aucun fournisseur IA commercial n'est configuré. Lancez configure_ai.bat pour ajouter une clé NVIDIA ou OpenAI sans réinstaller les dépendances.")
        else:
            cols = st.columns(len(configured))
            for col, provider_meta in zip(cols, configured):
                with col:
                    pname = provider_meta.get("provider")
                    pmodel = provider_meta.get("model")
                    st.markdown(f"**{pname}**  \n{pmodel}")
                    st.caption("Test prudent : jusqu'à 10 appels API, avec réutilisation du cache si le même cas a déjà été testé.")
                    if st.button(f"Tester l'arbitrage {pname}", key=f"arb_{pname}", use_container_width=True):
                        with st.spinner(f"Évaluation de {pname}…"):
                            rr = api_post(f"/api/v2/evaluation/run-arbitrator?provider={pname}&max_cases=100&max_calls=10", timeout=1800)
                            if rr.ok:
                                st.success("Mesure d'arbitrage enregistrée.")
                            else:
                                st.error(rr.text)
        arb_results = api_get("/api/v2/evaluation/arbitration-results?limit=50", timeout=10).json().get("results", [])
        if arb_results:
            adf = pd.DataFrame(arb_results)
            adisplay = pd.DataFrame({
                "Fournisseur": adf["provider"],
                "Modèle": adf["model_name"],
                "Cas évalués": adf["cases"],
                "Bon code présent dans Top-5": (adf["retrieval_coverage"] * 100).round(1).astype(str) + " %",
                "Top-1 local avant arbitrage": (adf["baseline_top1_accuracy"] * 100).round(1).astype(str) + " %",
                "Bon choix IA sur cas testés": (adf["arbitration_accuracy_on_covered"] * 100).round(1).astype(str) + " %",
                "Précision bout-en-bout mesurée": (adf["end_to_end_accuracy"] * 100).round(1).astype(str) + " %",
                "Abstentions": (adf["abstention_rate"] * 100).round(1).astype(str) + " %",
                "Appels API": adf["calls"],
                "Cache": adf["cache_hits"],
                "Temps moyen (ms)": adf["avg_latency_ms"].round(0),
            })
            st.dataframe(adisplay, use_container_width=True, hide_index=True)
            st.caption("Le taux de sortie invalide doit rester à 0 %. Toute proposition hors liste du référentiel est rejetée automatiquement par le garde-fou logiciel.")
            with st.expander("Mesures coût / sécurité", expanded=False):
                cols = [c for c in ["created_at","provider","model_name","calls","prompt_tokens","completion_tokens","invalid_output_rate","api_error_rate","cache_hits"] if c in adf.columns]
                st.dataframe(adf[cols], use_container_width=True, hide_index=True)
    except Exception:
        st.info("Le laboratoire d'arbitrage sera disponible dès que l'API CGS et un fournisseur IA sont configurés.")

