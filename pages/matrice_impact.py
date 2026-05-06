import streamlit as st
import pandas as pd
from streamlit_elements import elements, mui, nivo

from utils.db import read_table

# ==========================
# Constantes
# ==========================

TOTAL_EPCI_FRANCE = 1254  # Total des EPCI en France (dénominateur fixe)

# Palette de couleurs partagée
COULEUR_MINT = "#A4E7C7"
COULEUR_MINT_FONCE = "#7DD9B0"
COULEUR_BLEU = "#96C7DA"
COULEUR_BLEU_CLAIR = "#B8D6F7"
COULEUR_BLEU_PALE = "#D8EEFE"
COULEUR_PECHE = "#FFB595"
COULEUR_PECHE_CLAIR = "#FFD0BB"
COULEUR_VIOLET = "#E4CDEE"
COULEUR_VIOLET_FONCE = "#C49DD3"
COULEUR_VIOLET_CLAIR = "#E1E1FD"
COULEUR_GRIS = "#D9D9D9"

# Couleurs des graphes par section de la matrice d'impact
COULEUR_GRAPHE_UTILISE = COULEUR_PECHE       # Section "Utilisé" (badges orange)
COULEUR_GRAPHE_UTILE = COULEUR_BLEU          # Section "Utile" (badges bleu)
COULEUR_GRAPHE_IMPACTANT = COULEUR_BLEU      # Section "Impactant" (badges bleu)

# Thème Nivo partagé
theme_actif = {
    "text": {
        "fontFamily": "Source Sans Pro, sans-serif",
        "fontSize": 13,
        "fill": "#31333F"
    },
    "labels": {
        "text": {
            "fontFamily": "Source Sans Pro, sans-serif",
            "fontSize": 13,
            "fill": "#000000"
        }
    },
    "tooltip": {
        "container": {
            "background": "rgba(255, 255, 255, 0.95)",
            "color": "#31333F",
            "fontSize": "13px",
            "fontFamily": "Source Sans Pro, sans-serif",
            "borderRadius": "4px",
            "boxShadow": "0 2px 8px rgba(0,0,0,0.15)",
            "padding": "8px 12px",
            "border": "1px solid rgba(0, 0, 0, 0.1)"
        }
    }
}


# ==========================
# Chargement des données
# ==========================

@st.cache_resource(ttl="2d")
def load_data():
    df_user_actifs_ct_mois = read_table('user_actifs_ct_mois')
    df_activite_semaine = read_table('activite_semaine')
    df_ct_actives = read_table('ct_actives')
    df_pap_52 = read_table('pap_statut_5_fiches_modifiees_52_semaines')
    df_fap_52 = read_table('fa_distrib')
    nps = read_table('nps')
    return df_user_actifs_ct_mois, df_activite_semaine, df_ct_actives, df_pap_52, df_fap_52, nps


df_user_actifs_ct_mois, df_activite_semaine, df_ct_actives, df_pap_52, df_fap_52, nps = load_data()

# Exclusion BE/conseillers/internes via intersection des emails avec activite_semaine
df_user_actifs_ct_mois = df_user_actifs_ct_mois[
    df_user_actifs_ct_mois.email.isin(df_activite_semaine.email.to_list())
].copy()

# Normalisation des dates (gestion tz aware + alignement sur début de mois)
df_user_actifs_ct_mois['mois'] = pd.to_datetime(df_user_actifs_ct_mois['mois'], errors='coerce')
if getattr(df_user_actifs_ct_mois['mois'].dt, 'tz', None) is not None:
    df_user_actifs_ct_mois['mois'] = df_user_actifs_ct_mois['mois'].dt.tz_localize(None)
df_user_actifs_ct_mois = df_user_actifs_ct_mois.dropna(subset=['mois', 'email']).copy()
df_user_actifs_ct_mois['mois'] = df_user_actifs_ct_mois['mois'].dt.to_period('M').dt.to_timestamp()


# ==========================
# Helpers
# ==========================

def _last_complete_month(today: pd.Timestamp | None = None) -> pd.Timestamp:
    """Retourne le 1er jour du dernier mois complet (mois précédent le mois en cours)."""
    if today is None:
        today = pd.Timestamp.now().normalize()
    current_month = today.to_period('M').to_timestamp()
    return (current_month - pd.DateOffset(months=1)).normalize()


MOIS_REF = _last_complete_month()
MOIS_REF_M12 = (MOIS_REF - pd.DateOffset(months=12)).normalize()


def _format_mois_fr(ts: pd.Timestamp) -> str:
    mois_fr = {
        1: "janvier", 2: "février", 3: "mars", 4: "avril",
        5: "mai", 6: "juin", 7: "juillet", 8: "août",
        9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre"
    }
    return f"{mois_fr.get(ts.month, ts.month)} {ts.year}"


_MOIS_FR_ABREG = {
    1: "janv.", 2: "févr.", 3: "mars", 4: "avr.",
    5: "mai", 6: "juin", 7: "juil.", 8: "août",
    9: "sept.", 10: "oct.", 11: "nov.", 12: "déc."
}


def _label_mois_court(ts: pd.Timestamp) -> str:
    """Label compact pour l'axe X (ex: 'janv. 24')."""
    return f"{_MOIS_FR_ABREG.get(ts.month, ts.month)} {str(ts.year)[2:]}"


def _liste_24m(mois_fin: pd.Timestamp) -> list[pd.Timestamp]:
    """Retourne les 24 derniers mois (du plus ancien au plus récent inclus)."""
    return [(mois_fin - pd.DateOffset(months=i)).normalize() for i in range(23, -1, -1)]


def _serie_nivo(
    mois_list: list[pd.Timestamp],
    valeur_fn,
    serie_id: str = "serie",
) -> list[dict]:
    """Construit le format Nivo Line pour une série mensuelle."""
    return [{
        "id": serie_id,
        "data": [
            {"x": _label_mois_court(m), "y": float(valeur_fn(m))}
            for m in mois_list
        ]
    }]


def kpi_card(
    label: str,
    valeur_actuelle: float,
    valeur_precedente: float | None = None,
    fmt: str = "number",
    suffixe: str = "",
    delta_color: str = "normal",
    help_text: str | None = None,
):
    """Affiche un st.metric uniforme.

    Paramètres :
    - fmt : "number" (entier formaté) ou "percent" (en %, arrondi à l'entier)
    - suffixe : suffixe à coller à la valeur (ex: " utilisateurs")
    """
    if fmt == "percent":
        val_str = f"{int(round(valeur_actuelle * 100))}%"
        if valeur_precedente is not None:
            delta = (valeur_actuelle - valeur_precedente) * 100
            delta_str = f"{int(round(delta)):+d} pts"
        else:
            delta_str = None
    else:
        val_str = f"{int(round(valeur_actuelle)):,}".replace(",", " ") + suffixe
        if valeur_precedente is not None:
            delta = valeur_actuelle - valeur_precedente
            delta_str = f"{int(round(delta)):+,}".replace(",", " ")
        else:
            delta_str = None

    st.metric(label, val_str, delta=delta_str, delta_color=delta_color, help=help_text)


def kpi_chart_card(
    key: str,
    badge_label: str,
    badge_icon: str,
    badge_color: str,
    markdown_phrase: str,
    help_text: str,
    chart_data: list[dict],
    y_legend: str,
    chart_color: str = COULEUR_GRAPHE_UTILE,
    fmt: str = "number",
    height: int = 400,
):
    """Affiche un bloc badge + phrase markdown (avec help) + graphe Nivo Line.

    Paramètres :
    - key : identifiant unique pour `elements()` (doit être unique par appel sur la page).
    - markdown_phrase : phrase pré-formatée (avec valeurs et delta en gras) à afficher au-dessus du graphe.
    - chart_data : données au format Nivo Line ([{"id": ..., "data": [{"x": ..., "y": ...}, ...]}]).

    - fmt : "number" (axe Y en valeurs entières) ou "percent" (axe Y formaté en %, max=1).
    """
    st.badge(badge_label, icon=badge_icon, color=badge_color)
    st.markdown(markdown_phrase, help=help_text)

    if fmt == "percent":
        y_scale = {"type": "linear", "min": 0, "max": 1, "stacked": False, "reverse": False}
        axis_left_format = " >-.0%"
        y_format = " >-.2%"
    else:
        y_scale = {"type": "linear", "min": 0, "max": "auto", "stacked": False, "reverse": False}
        axis_left_format = None
        y_format = None

    axis_left = {
        "tickSize": 5,
        "tickPadding": 5,
        "tickRotation": 0,
        "legend": y_legend,
        "legendPosition": "middle",
        "legendOffset": -70,
    }
    if axis_left_format:
        axis_left["format"] = axis_left_format

    line_kwargs = dict(
        data=chart_data,
        margin={"top": 20, "right": 30, "bottom": 60, "left": 90},
        xScale={"type": "point"},
        yScale=y_scale,
        curve="monotoneX",
        axisTop=None,
        axisRight=None,
        axisBottom={
            "tickSize": 5,
            "tickPadding": 5,
            "tickRotation": -45,
        },
        axisLeft=axis_left,
        enableArea=True,
        areaOpacity=0.6,
        enablePoints=False,
        useMesh=True,
        enableSlices="x",
        colors=[chart_color],
        theme=theme_actif,
    )
    if y_format:
        line_kwargs["yFormat"] = y_format

    with elements(key):
        with mui.Box(sx={"height": height}):
            nivo.Line(**line_kwargs)


# ==========================
# Pré-calculs partagés
# ==========================

# Set des collectivites EPCI (categorie == 'EPCI')
epci_ids = set(
    df_ct_actives.loc[df_ct_actives['categorie'] == 'EPCI', 'collectivite_id']
                  .dropna()
                  .unique()
                  .tolist()
)


def collectivites_actives_12m(mois_fin: pd.Timestamp) -> set:
    """Set des collectivite_id avec au moins une activité sur les 12 mois finissant à mois_fin (inclus)."""
    mois_debut = (mois_fin - pd.DateOffset(months=11)).normalize()
    mask = (df_user_actifs_ct_mois['mois'] >= mois_debut) & (df_user_actifs_ct_mois['mois'] <= mois_fin)
    return set(df_user_actifs_ct_mois.loc[mask, 'collectivite_id'].dropna().unique().tolist())


def epci_avec_pap_actif_52(mois_fin: pd.Timestamp) -> set:
    """Set des collectivite_id (EPCI) ayant au moins un PAP avec statut='actif' au mois_fin."""
    df = df_pap_52.copy()
    df['mois'] = pd.to_datetime(df['mois'], errors='coerce').dt.to_period('M').dt.to_timestamp()
    df = df[(df['mois'] == mois_fin) & (df['statut'] == 'actif')]
    return set(df['collectivite_id'].dropna().unique().tolist())


def retention_4_sur_12(mois_fin: pd.Timestamp) -> tuple[int, int]:
    """Retourne (nb_ct_retenues, nb_ct_actives) sur la fenêtre 12 mois finissant à mois_fin."""
    mois_debut = (mois_fin - pd.DateOffset(months=11)).normalize()
    df = df_user_actifs_ct_mois[
        (df_user_actifs_ct_mois['mois'] >= mois_debut)
        & (df_user_actifs_ct_mois['mois'] <= mois_fin)
    ]
    if df.empty:
        return 0, 0
    nb_mois_par_ct = df.groupby('collectivite_id')['mois'].nunique()
    nb_ct_actives = int(nb_mois_par_ct.shape[0])
    nb_ct_retenues = int((nb_mois_par_ct >= 4).sum())
    return nb_ct_retenues, nb_ct_actives


def utilisateurs_actifs_du_mois(mois: pd.Timestamp) -> int:
    """Nombre d'utilisateurs uniques actifs au mois donné."""
    df = df_user_actifs_ct_mois[df_user_actifs_ct_mois['mois'] == mois]
    return int(df['email'].nunique())


def utilisateurs_actifs_12m(mois_fin: pd.Timestamp) -> int:
    """Nombre d'utilisateurs uniques actifs sur les 12 mois finissant à mois_fin (inclus)."""
    mois_debut = (mois_fin - pd.DateOffset(months=11)).normalize()
    mask = (df_user_actifs_ct_mois['mois'] >= mois_debut) & (df_user_actifs_ct_mois['mois'] <= mois_fin)
    return int(df_user_actifs_ct_mois.loc[mask, 'email'].nunique())


def pap_actifs_52_du_mois(mois: pd.Timestamp) -> int:
    """Nombre de PAP actifs (statut='actif', définition 52 semaines) au mois donné."""
    df = df_pap_52.copy()
    df['mois'] = pd.to_datetime(df['mois'], errors='coerce').dt.to_period('M').dt.to_timestamp()
    df = df[(df['mois'] == mois) & (df['statut'] == 'actif')]
    return int(df['plan'].nunique())


def fap_actifs_52_semaines(mois: pd.Timestamp) -> int:
    """Nombre de FAP actives (fiches d'action pilotables, statut='actif', définition 52 semaines) au mois donné."""
    df = df_fap_52.copy()
    df['mois'] = pd.to_datetime(df['mois'], errors='coerce').dt.to_period('M').dt.to_timestamp()
    df = df[(df['mois'] == mois)]
    return int(df['action_pilotable_actives'].sum())


# ==========================
# Interface
# ==========================

# ==========================
# 1. UTILISABLE
# ==========================
# st.markdown("---")
# st.markdown("## 1. Utilisable")
# st.info("En attente de la collecte des retours utilisateurs.")


# ==========================
# Helpers de formatage des phrases markdown
# ==========================

def _fmt_int_fr(v: float) -> str:
    """Formate un entier avec espace fine comme séparateur de milliers."""
    return f"{int(round(v)):,}".replace(",", " ")


def _fmt_delta_int_fr(v: float) -> str:
    """Formate un delta entier avec espace fine. Le signe '-' est conservé, le '+' est omis."""
    return f"{int(round(v)):,}".replace(",", " ")


# ==========================
# Pré-calcul des séries 24 mois
# ==========================

MOIS_24 = _liste_24m(MOIS_REF)


def _serie_users_actifs(m):
    return utilisateurs_actifs_du_mois(m)


def _serie_activation_epci(m):
    return len(collectivites_actives_12m(m) & epci_ids) / TOTAL_EPCI_FRANCE if TOTAL_EPCI_FRANCE else 0


def _serie_epci_pilotage(m):
    actifs = collectivites_actives_12m(m) & epci_ids
    avec_pap = epci_avec_pap_actif_52(m) & epci_ids
    return len(actifs & avec_pap) / TOTAL_EPCI_FRANCE if TOTAL_EPCI_FRANCE else 0


def _serie_retention(m):
    nb_ret, nb_act = retention_4_sur_12(m)
    return (nb_ret / nb_act) if nb_act else 0


def _serie_fap(m):
    return fap_actifs_52_semaines(m)


def _serie_pap(m):
    return pap_actifs_52_du_mois(m)


# ==========================
# 2. UTILISÉ
# ==========================
st.markdown("## 1. Utilisé")

# --- Utilisateurs actifs ---
nb_users_actuel = utilisateurs_actifs_du_mois(MOIS_REF)
nb_users_precedent = utilisateurs_actifs_du_mois(MOIS_REF_M12)
delta_users = nb_users_actuel - nb_users_precedent
sens_users = "de plus" if delta_users >= 0 else "de moins"

kpi_chart_card(
    key="chart_users_actifs",
    badge_label="Activité",
    badge_icon=":material/person_check:",
    badge_color="orange",
    markdown_phrase=(
        f"Territoires en Transitions comptait **{_fmt_int_fr(nb_users_actuel)} utilisateurs actifs** "
        f"en {_format_mois_fr(MOIS_REF)}. C'est **{_fmt_delta_int_fr(delta_users)} {sens_users}** "
        f"qu'il y a un an."
    ),
    help_text=(
        f"Nombre d'utilisateurs actifs au cours de {_format_mois_fr(MOIS_REF)}. "
        "Tout utilisateurs confondu : agents, conseillers, bureaux d'études, etc."
    ),
    chart_data=_serie_nivo(MOIS_24, _serie_users_actifs, serie_id="Utilisateurs actifs"),
    y_legend="Utilisateurs actifs",
    chart_color=COULEUR_GRAPHE_UTILISE,
    fmt="number",
)

# --- Activation des EPCI ---
epci_actifs_12m = collectivites_actives_12m(MOIS_REF) & epci_ids
epci_actifs_12m_prev = collectivites_actives_12m(MOIS_REF_M12) & epci_ids
taux_penetration_actuel = len(epci_actifs_12m) / TOTAL_EPCI_FRANCE if TOTAL_EPCI_FRANCE else 0
taux_penetration_prev = len(epci_actifs_12m_prev) / TOTAL_EPCI_FRANCE if TOTAL_EPCI_FRANCE else 0
delta_pen = (taux_penetration_actuel - taux_penetration_prev) * 100
sens_pen = "de plus" if delta_pen >= 0 else "de moins"

kpi_chart_card(
    key="chart_activation_epci",
    badge_label="Taux de pénétration",
    badge_icon=":material/trending_up:",
    badge_color="green",
    markdown_phrase=(
        f"**{taux_penetration_actuel * 100:.0f}% des EPCI** étaient actifs sur Territoires en Transitions en {_format_mois_fr(MOIS_REF)}. "
        f" C'est **{delta_pen:.0f} pts {sens_pen}** "
        f"qu'il y a un an."
    ),
    help_text="% d'EPCI avec au moins un utilisateur actif sur les 12 derniers mois.",
    chart_data=_serie_nivo(MOIS_24, _serie_activation_epci, serie_id="Activation des EPCI"),
    y_legend="Activation des EPCI",
    chart_color=COULEUR_MINT,
    fmt="percent",
)

# --- EPCI en pilotage ---
epci_pap_actuel = epci_avec_pap_actif_52(MOIS_REF) & epci_ids
epci_pap_prev = epci_avec_pap_actif_52(MOIS_REF_M12) & epci_ids
set_a_actuel = epci_actifs_12m & epci_pap_actuel
set_a_prev = epci_actifs_12m_prev & epci_pap_prev
taux_complet_actuel = len(set_a_actuel) / TOTAL_EPCI_FRANCE if TOTAL_EPCI_FRANCE else 0
taux_complet_prev = len(set_a_prev) / TOTAL_EPCI_FRANCE if TOTAL_EPCI_FRANCE else 0
delta_complet = (taux_complet_actuel - taux_complet_prev) * 100
sens_complet = "de plus" if delta_complet >= 0 else "de moins"

kpi_chart_card(
    key="chart_epci_pilotage",
    badge_label="Utilisations complètes",
    badge_icon=":material/check_circle:",
    badge_color="green",
    markdown_phrase=(
        f"**{taux_complet_actuel * 100:.0f}% des EPCI** avaient au moins un plan d'action pilotable "
        f"actif en {_format_mois_fr(MOIS_REF)}. C'est **{delta_complet:.0f} pts {sens_complet}** "
        f"qu'il y a un an."
    ),
    help_text=(
        "Un plan d'action pilotable actif est un plan dont 5 fiches, avec au moins un titre, "
        "une personne pilote et un statut, ont modifiées sur les 12 derniers mois."
    ),
    chart_data=_serie_nivo(MOIS_24, _serie_epci_pilotage, serie_id="EPCI en pilotage"),
    y_legend="EPCI en pilotage",
    chart_color=COULEUR_MINT,
    fmt="percent",
)

# --- Rétention des collectivités ---
nb_ret_actuel, nb_act_actuel = retention_4_sur_12(MOIS_REF)
nb_ret_prev, nb_act_prev = retention_4_sur_12(MOIS_REF_M12)
taux_retention_actuel = (nb_ret_actuel / nb_act_actuel) if nb_act_actuel else 0
taux_retention_prev = (nb_ret_prev / nb_act_prev) if nb_act_prev else 0
delta_ret = (taux_retention_actuel - taux_retention_prev) * 100
sens_ret = "de plus" if delta_ret >= 0 else "de moins"

kpi_chart_card(
    key="chart_retention",
    badge_label="Taux de rétention",
    badge_icon=":material/radio_button_checked:",
    badge_color="orange",
    markdown_phrase=(
        f"**{taux_retention_actuel * 100:.0f}% des collectivités** avec un profil sur Territoires en Transitions étaient en rétention en {_format_mois_fr(MOIS_REF)}."
        f" C'est **{delta_ret:.0f} pts {sens_ret}** qu'il y a un an."
    ),
    help_text=("Parmis toutes les collectivités avec un profil (au moins un agent rattaché à la collectivité),"
        " % des collectivités s'étant connectées au moins 1 fois sur 4 mois différents "
        "au cours des 12 derniers mois. Métrique choisie pour rendre compte de la temporalité "
        "de l'usage de la plateforme par les agents des collectivités (suivi trimestriel)."
    ),
    chart_data=_serie_nivo(MOIS_24, _serie_retention, serie_id="Rétention"),
    y_legend="Rétention",
    chart_color=COULEUR_GRAPHE_UTILISE,
    fmt="percent",
)


# ==========================
# 3. UTILE
# ==========================
st.markdown("---")
st.markdown("## 2. Utile")

# --- NPS (kpi_card classique, pas de graphe demandé) ---
st.badge("Satisfaction des utilisateurs", icon=":material/thumb_up_off_alt:", color="blue")
nps_moyen_actuel = nps['nps'].iloc[0]
col_nps, _, _ = st.columns(3)
with col_nps:
    kpi_card(
        label="NPS",
        valeur_actuelle=nps_moyen_actuel,
        fmt="number",
        help_text=(
            f"Le Net Promoter Score (NPS) est un système de mesure de la satisfaction des utilisateurs. Il évalue la probabilité "
            "qu'un utilisateur recommande Territoires en Transitions à un collègue sur une échelle de 1 à 10. Un score entre -100 et +100 est ensuite calculé. "
            "Au dessus de 0 est bon, au dessus de 20 est favorable, au dessus de 50 est excellent, au dessus de 80 est world class."
        ),
    )

# --- Fiches actions pilotables actives ---
nb_fap_actifs_actuel = fap_actifs_52_semaines(MOIS_REF)
nb_fap_actifs_prev = fap_actifs_52_semaines(MOIS_REF_M12)
delta_fap = nb_fap_actifs_actuel - nb_fap_actifs_prev
sens_fap = "de plus" if delta_fap >= 0 else "de moins"

kpi_chart_card(
    key="chart_fap",
    badge_label="Pilotage des actions de la transition écologique",
    badge_icon=":material/add_notes:",
    badge_color="blue",
    markdown_phrase=(
        f"**{_fmt_int_fr(nb_fap_actifs_actuel)} actions actives** étaient sur Territoires en Transitions en {_format_mois_fr(MOIS_REF)}. "
        f"C'est **{_fmt_delta_int_fr(delta_fap)} "
        f"{sens_fap}** qu'il y a un an."
    ),
    help_text=(
        f"Une action active est une fiche, avec au moins un titre, une personne "
        "pilote et un statut, qui a été modifiée sur les 12 derniers mois."
    ),
    chart_data=_serie_nivo(MOIS_24, _serie_fap, serie_id="Fiches actions"),
    y_legend="Fiches actions",
    chart_color=COULEUR_GRAPHE_UTILE,
    fmt="number",
)


# ==========================
# 4. IMPACTANT
# ==========================
st.markdown("---")
st.markdown("## 3. Impactant")

nb_pap_actifs_actuel = pap_actifs_52_du_mois(MOIS_REF)
nb_pap_actifs_prev = pap_actifs_52_du_mois(MOIS_REF_M12)
delta_pap = nb_pap_actifs_actuel - nb_pap_actifs_prev
sens_pap = "de plus" if delta_pap >= 0 else "de moins"

kpi_chart_card(
    key="chart_pap",
    badge_label="Pilotage de la transition écologique",
    badge_icon=":material/globe_book:",
    badge_color="blue",
    markdown_phrase=(
        f"Territoires en Transitions comptait **{_fmt_int_fr(nb_pap_actifs_actuel)} plans d'action "
        f"pilotables actifs** en {_format_mois_fr(MOIS_REF)}. C'est **{_fmt_delta_int_fr(delta_pap)} "
        f"{sens_pap}** qu'il y a un an."
    ),
    help_text=(
        f"Nombre de plans d'action pilotables actifs en {_format_mois_fr(MOIS_REF)}. "
        "Un plan d'action pilotable actif est un plan dont 5 fiches, avec au moins un titre, "
        "une personne pilote et un statut, ont modifiées sur les 12 derniers mois."
    ),
    chart_data=_serie_nivo(MOIS_24, _serie_pap, serie_id="Plans d'action"),
    y_legend="Plans d'action pilotables actifs",
    chart_color=COULEUR_GRAPHE_IMPACTANT,
    fmt="number",
)


# ==========================
# 5. EFFICIENT
# ==========================
st.markdown("---")
st.markdown("## 4. Efficient")

BUDGET_ANNUEL = 1_600_000  # Budget annuel brut alloué à la plateforme (€)

mois_debut_12m = (MOIS_REF - pd.DateOffset(months=11)).normalize()
mois_debut_12m_prev = (MOIS_REF_M12 - pd.DateOffset(months=11)).normalize()

nb_users_12m_actuel = utilisateurs_actifs_12m(MOIS_REF)
nb_users_12m_prev = utilisateurs_actifs_12m(MOIS_REF_M12)

nb_ct_12m_actuel = len(collectivites_actives_12m(MOIS_REF))
nb_ct_12m_prev = len(collectivites_actives_12m(MOIS_REF_M12))

col_b, col_u, col_c, col_a = st.columns(4)

# --- Budget annuel brut ---
with col_b:
    st.badge("Budget", icon=":material/account_balance:", color="violet")
    kpi_card(
        label="Budget annuel brut",
        valeur_actuelle=BUDGET_ANNUEL,
        fmt="number",
        suffixe=" €",
        help_text="Budget annuel brut alloué à la plateforme Territoires en Transitions.",
    )

# --- Coût par utilisateur actif (12 mois) ---
with col_u:
    st.badge("Coût d'usage", icon=":material/payments:", color="violet")
    cout_user_actuel = (BUDGET_ANNUEL / nb_users_12m_actuel) if nb_users_12m_actuel else 0
    cout_user_prev = (BUDGET_ANNUEL / nb_users_12m_prev) if nb_users_12m_prev else 0
    kpi_card(
        label="Coût par utilisateur actif",
        valeur_actuelle=cout_user_actuel,
        valeur_precedente=cout_user_prev,
        fmt="number",
        suffixe=" €",
        delta_color="inverse",
        help_text=(
            f"Budget annuel brut divisé par le nombre d'utilisateurs uniques actifs "
            f"sur les 12 derniers mois (de {_format_mois_fr(mois_debut_12m)} à {_format_mois_fr(MOIS_REF)}). "
            f"Comparé à la même fenêtre 12 mois finissant en {_format_mois_fr(MOIS_REF_M12)}."
        ),
    )

# --- Coût par collectivité active (12 mois) ---
with col_c:
    st.badge("Coût d'usage", icon=":material/payments:", color="violet")
    cout_ct_actuel = (BUDGET_ANNUEL / nb_ct_12m_actuel) if nb_ct_12m_actuel else 0
    cout_ct_prev = (BUDGET_ANNUEL / nb_ct_12m_prev) if nb_ct_12m_prev else 0
    kpi_card(
        label="Coût par collectivité active",
        valeur_actuelle=cout_ct_actuel,
        valeur_precedente=cout_ct_prev,
        fmt="number",
        suffixe=" €",
        delta_color="inverse",
        help_text=(
            f"Budget annuel brut divisé par le nombre de collectivités actives "
            f"sur les 12 derniers mois (de {_format_mois_fr(mois_debut_12m)} à {_format_mois_fr(MOIS_REF)}). "
            f"Comparé à la même fenêtre 12 mois finissant en {_format_mois_fr(MOIS_REF_M12)}."
        ),
    )

# --- Coût par fiche action pilotable active ---
with col_a:
    st.badge("Coût d'usage", icon=":material/payments:", color="violet")
    cout_fap_actuel = (BUDGET_ANNUEL / nb_fap_actifs_actuel) if nb_fap_actifs_actuel else 0
    cout_fap_prev = (BUDGET_ANNUEL / nb_fap_actifs_prev) if nb_fap_actifs_prev else 0
    kpi_card(
        label="Coût par action pilotable active",
        valeur_actuelle=cout_fap_actuel,
        valeur_precedente=cout_fap_prev,
        fmt="number",
        suffixe=" €",
        delta_color="inverse",
        help_text=(
            f"Budget annuel brut divisé par le nombre de fiches actions pilotables actives "
            f"en {_format_mois_fr(MOIS_REF)} (définition 52 semaines)."
        ),
    )
