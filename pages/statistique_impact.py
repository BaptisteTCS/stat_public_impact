import streamlit as st
import pandas as pd
from streamlit_elements import elements, nivo, mui

st.set_page_config(layout="wide")

from utils.db import (
    read_table
)


# ===================================================
# CONFIGURATION : Thème visuel pour les graphiques Nivo
# ===================================================

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

DATE_DEBUT_GRAPHES = pd.Timestamp("2024-01-01")


# ===================================================
# DONNÉES : Chargement depuis la base de données
# Les données sont mises en cache pendant 2 jours
# pour éviter des requêtes répétées à chaque interaction.
# ===================================================

@st.cache_resource(ttl="2d")
def load_data():
    df_ct_actives = read_table('ct_actives')
    df_ct_users_actifs = read_table('user_actifs_ct_mois')
    df_pap = read_table('passage_pap_region')
    df_fap = read_table('evolution_fa_region')
    df_ind_perso = read_table('evolution_ind_pers')
    df_ind_od = read_table('evolution_ind_od')
    df_ind_od_producteur = read_table('ind_od_producteur_indicateur')
    return df_ct_actives, df_ct_users_actifs, df_fap, df_pap, df_ind_perso, df_ind_od, df_ind_od_producteur

df_ct_actives, df_ct_users_actifs, df_fap, df_pap, df_ind_perso, df_ind_od, df_ind_od_producteur = load_data()


# ===================================================
# FILTRES : Sélection du territoire (région / département)
# Chaque filtre dépend du précédent (cascade région → département).
# ===================================================

selects = st.columns(2)
with selects[0]:
    regions = ["Toutes"] + sorted(df_ct_actives["region_name"].dropna().unique().tolist())
    selected_region = st.selectbox("Région", options=regions, index=0)

with selects[1]:
    # Les départements sont filtrés selon la région sélectionnée
    if selected_region == "Toutes":
        departements = ["Tous"] + sorted(df_ct_actives["departement_name"].dropna().unique().tolist())
    else:
        departements = ["Tous"] + sorted(df_ct_actives[df_ct_actives["region_name"] == selected_region]["departement_name"].dropna().unique().tolist())
    selected_departement = st.selectbox("Département", options=departements, index=0)


# ===================================================
# SECTION 1 : Activation des collectivités sur TET
# Affiche le nombre de collectivités actives par catégorie,
# ainsi qu'un total global, pour le territoire sélectionné.
# ===================================================

st.markdown("*La sélection d'un territoire s'applique à toute la page.*")
st.markdown("---")

# Badge indiquant le périmètre géographique actif
if selected_region != "Toutes" and selected_departement == "Tous":
    st.badge(f'Profils de collectivités : **{selected_region}**', icon=":material/trending_up:", color="green")
elif selected_region != "Toutes" and selected_departement != "Tous":
    st.badge(f'Profils de collectivités : **{selected_departement}**', icon=":material/trending_up:", color="green")
else:
    st.badge(f'Profils de collectivités : **Territoire national**', icon=":material/trending_up:", color="green")

# Application des filtres géographiques sur le dataframe principal
df_ct_actives_selected = df_ct_actives.copy()
if selected_region != "Toutes":
    df_ct_actives_selected = df_ct_actives_selected[df_ct_actives_selected["region_name"] == selected_region]
if selected_departement != "Tous":
    df_ct_actives_selected = df_ct_actives_selected[df_ct_actives_selected["departement_name"] == selected_departement]

# Ordre d'affichage souhaité pour les catégories
ordre_prioritaire = ["EPCI", "Syndicats", "PETR", "Communes"]

cats = sorted(
    df_ct_actives_selected["categorie"].dropna().unique(),
    key=lambda c: ordre_prioritaire.index(c)
    if c in ordre_prioritaire
    else len(ordre_prioritaire)
)

# Conversion de la date d'activation en datetime sans timezone
df_ct_actives_selected["date_activation"] = pd.to_datetime(
    df_ct_actives_selected["date_activation"],
    errors='coerce',
    utc=False
).dt.tz_localize(None)

# --- Affichage des métriques : Total global + détail par catégorie ---

# Ligne du total global (affiché en premier, seul sur sa ligne)
_nb_ct = f"{int(df_ct_actives_selected.shape[0]):,}".replace(",", "\u202f")
if selected_region == "Toutes" and selected_departement == "Tous":
    st.markdown(f"Sur le **territoire national**, **{_nb_ct} collectivités** ont créé un profil sur Territoires en Transitions.")
elif selected_region != "Toutes" and selected_departement == "Tous":
    st.markdown(f"Sur la région **{selected_region}**, **{_nb_ct} collectivités** ont créé un profil sur Territoires en Transitions.")
elif selected_region != "Toutes" and selected_departement != "Tous":
    st.markdown(f"Sur le département **{selected_departement}**, **{_nb_ct} collectivités** ont créé un profil sur Territoires en Transitions.")

# Lignes du détail par catégorie (max 6 colonnes par ligne)
max_cols = 6
for row_start in range(0, len(cats), max_cols):
    row_cats = cats[row_start:row_start + max_cols]
    cols = st.columns(len(row_cats))

    for col, cat in zip(cols, row_cats):
        with col:
            df_cat = df_ct_actives_selected[df_ct_actives_selected["categorie"] == cat]
            st.metric(cat, int(df_cat.shape[0]))

# ===================================================
# SECTION 2 : Évolution cumulée des collectivités par catégorie
# Graphique en aires empilées montrant la progression
# mensuelle du nombre de collectivités activées.
# ===================================================

# Calcul du nombre cumulé d'activations par mois et par catégorie
df_ct_actives_selected['mois'] = df_ct_actives_selected['date_activation'].dt.to_period('M')
df_evolution = df_ct_actives_selected.groupby(['mois', 'categorie']).size().reset_index(name='nb_ct')
df_evolution['nb_ct_cumule'] = df_evolution.groupby('categorie')['nb_ct'].cumsum()

all_mois = sorted(df_ct_actives_selected['mois'].dropna().unique())
all_categories = df_ct_actives_selected['categorie'].dropna().unique()

if len(all_mois) == 0:
    st.info("Aucune donnée disponible pour les filtres sélectionnés.")
else:
    # Tri des catégories par volume décroissant au dernier mois connu
    # (la catégorie la plus grande est placée en bas du graphique empilé)
    dernier_mois = max(all_mois)
    totaux_dernier_mois = {}
    for cat in all_categories:
        df_cat = df_evolution[df_evolution['categorie'] == cat]
        totaux_dernier_mois[cat] = df_cat['nb_ct_cumule'].iloc[-1] if not df_cat.empty else 0

    categories_triees = sorted(all_categories, key=lambda c: totaux_dernier_mois.get(c, 0), reverse=True)

    # Construction des séries pour Nivo Line :
    # on bouche les trous temporels avec un forward-fill (valeur précédente)
    # afin d'obtenir une courbe cumulative continue.
    area_data_ct_evolution = []
    for cat in categories_triees:
        df_filtered = df_evolution[df_evolution['categorie'] == cat].copy()
        if not df_filtered.empty:
            df_all_mois = pd.DataFrame({'mois': all_mois})
            df_complete = df_all_mois.merge(df_filtered[['mois', 'nb_ct_cumule']], on='mois', how='left')
            df_complete['nb_ct_cumule'] = df_complete['nb_ct_cumule'].ffill().fillna(0).astype(int)

            area_data_ct_evolution.append({
                "id": cat,
                "data": [
                    {"x": str(row['mois']), "y": row['nb_ct_cumule']}
                    for _, row in df_complete.iterrows()
                ]
            })

    with elements("area_ct_evolution"):
        with mui.Box(sx={"height": 500}):
            nivo.Line(
                data=area_data_ct_evolution,
                margin={"top": 20, "right": 180, "bottom": 50, "left": 60},
                xScale={"type": "point"},
                yScale={"type": "linear", "min": 0, "max": "auto", "stacked": True, "reverse": False},
                curve="monotoneX",
                axisTop=None,
                axisRight=None,
                axisBottom={
                    "tickSize": 5,
                    "tickPadding": 5,
                    "tickRotation": -45,
                    "legend": "",
                    "legendOffset": 45,
                    "legendPosition": "middle"
                },
                axisLeft={
                    "tickSize": 5,
                    "tickPadding": 5,
                    "tickRotation": 0,
                },
                enableArea=True,
                areaOpacity=0.7,
                enablePoints=False,
                useMesh=True,
                enableSlices="x",
                legends=[
                    {
                        "anchor": "bottom-right",
                        "direction": "column",
                        "justify": False,
                        "translateX": 100,
                        "translateY": 0,
                        "itemsSpacing": 2,
                        "itemWidth": 80,
                        "itemHeight": 20,
                        "itemDirection": "left-to-right",
                        "itemOpacity": 0.85,
                        "symbolSize": 12,
                        "symbolShape": "circle",
                    }
                ],
                colors={"scheme": "pastel2"},
                theme=theme_actif,
            )


# ===================================================
# SECTION 3 : Évolution de l'activité (glissant 12 mois)
# Graphique en aire montrant le nombre d'utilisateurs ou de collectivités
# uniques ayant été actifs au cours des 12 derniers mois, mois par mois.
# ===================================================
st.markdown("---")

if selected_region != "Toutes" and selected_departement == "Tous":
    st.badge(f'Activité : **{selected_region}**', icon=":material/bolt:", color="green")
elif selected_region != "Toutes" and selected_departement != "Tous":
    st.badge(f'Activité : **{selected_departement}**', icon=":material/bolt:", color="green")
else:
    st.badge(f'Activité : **Territoire national**', icon=":material/bolt:", color="green")

# Segmented control : choix du mode d'affichage
segment_activite = st.segmented_control(
    label="Afficher par",
    options=["Utilisateurs", "Collectivités"],
    default="Utilisateurs",
    key="segment_activite"
)

# Préparation du dataframe de base avec filtres géographiques
df_users = df_ct_users_actifs.copy()
df_users['mois'] = pd.to_datetime(df_users['mois'])

if selected_region != "Toutes":
    df_users = df_users[df_users["region_name"] == selected_region]
if selected_departement != "Tous":
    df_users = df_users[df_users["departement_name"] == selected_departement]

# Calcul du rolling 12 mois selon le mode sélectionné
if segment_activite == "Utilisateurs":
    df_users = df_users.drop_duplicates(['mois', 'email'])
    col_comptage = 'email'
    label_serie = "Utilisateurs actifs"
    label_axe = "Nombre d'utilisateurs"
    label_texte = "utilisateurs actifs"
else:
    df_users = df_users.drop_duplicates(['mois', 'collectivite_id'])
    col_comptage = 'collectivite_id'
    label_serie = "Collectivités actives"
    label_axe = "Nombre de collectivités"
    label_texte = "collectivités actives"

mois_list = sorted(df_users['mois'].unique())

out = []
for m in mois_list:
    mask = (df_users['mois'] <= m) & (df_users['mois'] > m - pd.DateOffset(months=12))
    out.append((m, df_users.loc[mask, col_comptage].nunique()))

df_final = pd.DataFrame(out, columns=['mois', 'valeur_12m'])

if df_final.empty:
    st.info("Aucune donnée disponible pour les filtres sélectionnés.")
else:
    derniere_valeur = f"{int(df_final['valeur_12m'].iloc[-1]):,}".replace(",", "\u202f")
    dernier_mois = df_final['mois'].iloc[-1].strftime('%B %Y')

    if selected_region != "Toutes" and selected_departement == "Tous":
        st.markdown(f"Sur la région **{selected_region}**, Territoires en Transitions compte **{derniere_valeur} {label_texte}** sur les 12 derniers mois.")
    elif selected_region != "Toutes" and selected_departement != "Tous":
        st.markdown(f"Sur le département **{selected_departement}**, Territoires en Transitions compte **{derniere_valeur} {label_texte}** sur les 12 derniers mois.")
    else:
        st.markdown(f"Sur le **territoire national**, Territoires en Transitions compte **{derniere_valeur} {label_texte}** sur les 12 derniers mois.")

    area_data_users = [
        {
            "id": label_serie,
            "data": [
                {"x": row['mois'].strftime('%Y-%m'), "y": int(row['valeur_12m'])}
                for _, row in df_final[df_final['mois'] >= DATE_DEBUT_GRAPHES].iterrows()
            ]
        }
    ]

    with elements("area_users_evolution"):
        with mui.Box(sx={"height": 500}):
            nivo.Line(
                data=area_data_users,
                margin={"top": 20, "right": 30, "bottom": 50, "left": 60},
                xScale={"type": "point"},
                yScale={"type": "linear", "min": 0, "max": "auto", "stacked": False, "reverse": False},
                curve="monotoneX",
                axisTop=None,
                axisRight=None,
                axisBottom={
                    "tickSize": 5,
                    "tickPadding": 5,
                    "tickRotation": -45,
                    "legend": "",
                    "legendOffset": 45,
                    "legendPosition": "middle"
                },
                axisLeft={
                    "tickSize": 5,
                    "tickPadding": 5,
                    "tickRotation": 0,
                },
                enableArea=True,
                areaOpacity=0.3,
                enablePoints=False,
                useMesh=True,
                enableSlices="x",
                colors=["#3b82f6"],
                theme=theme_actif,
            )

# --- Distribution du nombre d'utilisateurs actifs par collectivité (12 derniers mois glissants) ---

_dernier_mois_glissant = df_users['mois'].max()
_mask_12m = (
    (df_users['mois'] <= _dernier_mois_glissant) &
    (df_users['mois'] > _dernier_mois_glissant - pd.DateOffset(months=12))
)
df_users_12m = df_users.loc[_mask_12m]

df_distrib = (
    df_users_12m.groupby('collectivite_id')['email']
    .nunique()
    .reset_index(name='nb_users')
)

if not df_distrib.empty:
    _moyenne = int(df_distrib['nb_users'].mean())
    _max = int(df_distrib['nb_users'].max())

    if selected_region != "Toutes" and selected_departement == "Tous":
        _label_distrib = f"Sur la région **{selected_region}**"
    elif selected_region != "Toutes" and selected_departement != "Tous":
        _label_distrib = f"Sur le département **{selected_departement}**"
    else:
        _label_distrib = "Sur le **territoire national**"

    st.markdown(
        f"{_label_distrib}, les collectivités comptent en moyenne "
        f"**{_moyenne} utilisateurs actifs**, allant jusqu'à **{_max} utilisateurs actifs** sur les 12 derniers mois."
    )

    # Buckets fixes : 1, 2–5, 6–15, 16–30, 31–50, 50+
    _bin_edges = [1, 2, 6, 16, 31, 51, float('inf')]
    _bin_labels = ["1 utilisateur", "2–5 utilisateurs", "6–15 utilisateurs", "16–30 utilisateurs", "31–50 utilisateurs", "50+ utilisateurs"]
    df_distrib['bucket'] = pd.cut(df_distrib['nb_users'], bins=_bin_edges, right=False, labels=_bin_labels)
    df_hist = (
        df_distrib.groupby('bucket', observed=True)
        .size()
        .reset_index(name='nb_ct')
    )
    df_hist['label'] = df_hist['bucket'].astype(str)

    hist_data = [
        {"tranche": row['label'], "Collectivités": int(row['nb_ct'])}
        for _, row in df_hist.iterrows()
        if row['label']
    ]

    with elements("bar_distrib_users"):
        with mui.Box(sx={"height": 420}):
            nivo.Bar(
                data=hist_data,
                keys=["Collectivités"],
                indexBy="tranche",
                margin={"top": 20, "right": 30, "bottom": 70, "left": 60},
                padding=0.25,
                valueScale={"type": "linear"},
                indexScale={"type": "band", "round": True},
                colors=["#3b82f6"],
                borderRadius=3,
                axisTop=None,
                axisRight=None,
                axisBottom={
                    "tickSize": 5,
                    "tickPadding": 5,
                    "tickRotation": 0,
                    "legend": "Nombre d'utilisateurs actifs par collectivité",
                    "legendPosition": "middle",
                    "legendOffset": 60,
                },
                axisLeft={
                    "tickSize": 5,
                    "tickPadding": 5,
                    "tickRotation": 0,
                    "legend": "Nombre de collectivités",
                    "legendPosition": "middle",
                    "legendOffset": -50,
                },
                labelSkipHeight=12,
                enableLabel=True,
                labelTextColor={"from": "color", "modifiers": [["darker", 2]]},
                theme=theme_actif,
            )


# ===================================================
# SECTION 4 : Plans d'action et Fiches actions pilotables
# Deux graphiques côte à côte montrant l'évolution cumulée
# des PAP passés et des fiches actions pilotables.
# ===================================================

st.markdown("---")

if selected_region != "Toutes" and selected_departement == "Tous":
    st.badge(f'Plans & Fiches actions : **{selected_region}**', icon=":material/task:", color="blue")
elif selected_region != "Toutes" and selected_departement != "Tous":
    st.badge(f'Plans & Fiches actions : **{selected_departement}**', icon=":material/task:", color="blue")
else:
    st.badge(f'Plans & Fiches actions : **Territoire national**', icon=":material/task:", color="blue")

col_pap, col_fap = st.columns(2)

# --- Graphique PAP : nombre de lignes cumulées ---
with col_pap:

    df_pap_filtered = df_pap.copy()
    df_pap_filtered['mois'] = pd.to_datetime(df_pap_filtered['mois'])
    if selected_region != "Toutes":
        df_pap_filtered = df_pap_filtered[df_pap_filtered["region_name"] == selected_region]
    if selected_departement != "Tous":
        df_pap_filtered = df_pap_filtered[df_pap_filtered["departement_name"] == selected_departement]

    df_pap_evolution = (
        df_pap_filtered.groupby('mois')
        .size()
        .reset_index(name='nb')
        .sort_values('mois')
    )
    df_pap_evolution['nb_cumule'] = df_pap_evolution['nb'].cumsum()

    # Bouche les mois manquants avec la valeur cumulée du mois précédent
    if not df_pap_evolution.empty:
        all_months_pap = pd.date_range(
            df_pap_evolution['mois'].min(),
            df_pap_evolution['mois'].max(),
            freq='MS'
        )
        df_pap_evolution = (
            df_pap_evolution.set_index('mois')
            .reindex(all_months_pap)
            .rename_axis('mois')
            .reset_index()
        )
        df_pap_evolution['nb_cumule'] = df_pap_evolution['nb_cumule'].ffill().fillna(0).astype(int)

    if df_pap_evolution.empty:
        st.info("Aucune donnée PAP disponible.")
    else:
        derniere_val_pap = f"{int(df_pap_evolution['nb_cumule'].iloc[-1]):,}".replace(",", "\u202f")
        _help_pap = "Un plan d'action pilotable est un plan d'action qui comprend au moins 5 fiches actions pilotables."
        if selected_region != "Toutes" and selected_departement == "Tous":
            st.markdown(f"Sur la région **{selected_region}**, **{derniere_val_pap} plans d'actions pilotables** ont été déposés.", help=_help_pap)
        elif selected_region != "Toutes" and selected_departement != "Tous":
            st.markdown(f"Sur le département **{selected_departement}**, **{derniere_val_pap} plans d'actions pilotables** ont été déposés.", help=_help_pap)
        else:
            st.markdown(f"Sur le **territoire national**, **{derniere_val_pap} plans d'actions pilotables** ont été déposés.", help=_help_pap)

        pap_data = [
            {
                "id": "Plans d'action",
                "data": [
                    {"x": row['mois'].strftime('%Y-%m'), "y": int(row['nb_cumule'])}
                    for _, row in df_pap_evolution[df_pap_evolution['mois'] >= DATE_DEBUT_GRAPHES].iterrows()
                ]
            }
        ]

        with elements("area_pap_evolution"):
            with mui.Box(sx={"height": 400}):
                nivo.Line(
                    data=pap_data,
                    margin={"top": 20, "right": 30, "bottom": 50, "left": 60},
                    xScale={"type": "point"},
                    yScale={"type": "linear", "min": 0, "max": "auto", "stacked": False, "reverse": False},
                    curve="monotoneX",
                    axisTop=None,
                    axisRight=None,
                    axisBottom={
                        "tickSize": 5,
                        "tickPadding": 5,
                        "tickRotation": -45,
                        "legend": "",
                        "legendOffset": 45,
                        "legendPosition": "middle"
                    },
                    axisLeft={
                        "tickSize": 5,
                        "tickPadding": 5,
                        "tickRotation": 0,
                    },
                    enableArea=True,
                    areaOpacity=0.3,
                    enablePoints=False,
                    useMesh=True,
                    enableSlices="x",
                    colors=["#10b981"],
                    theme=theme_actif,
                )

# --- Graphique FAP : fiches actions pilotables (distinct fiche_id cumulées) ---
with col_fap:

    df_fap_filtered = df_fap.copy()
    df_fap_filtered['mois'] = pd.to_datetime(df_fap_filtered['mois'])
    if selected_region != "Toutes":
        df_fap_filtered = df_fap_filtered[df_fap_filtered["region_name"] == selected_region]
    if selected_departement != "Tous":
        df_fap_filtered = df_fap_filtered[df_fap_filtered["departement_name"] == selected_departement]

    df_fap_evolution = (
        df_fap_filtered.groupby('mois')['fiche_id']
        .nunique()
        .reset_index(name='nb')
        .sort_values('mois')
    )
    df_fap_evolution['nb_cumule'] = df_fap_evolution['nb'].cumsum()

    # Bouche les mois manquants avec la valeur cumulée du mois précédent
    if not df_fap_evolution.empty:
        all_months_fap = pd.date_range(
            df_fap_evolution['mois'].min(),
            df_fap_evolution['mois'].max(),
            freq='MS'
        )
        df_fap_evolution = (
            df_fap_evolution.set_index('mois')
            .reindex(all_months_fap)
            .rename_axis('mois')
            .reset_index()
        )
        df_fap_evolution['nb_cumule'] = df_fap_evolution['nb_cumule'].ffill().fillna(0).astype(int)

    if df_fap_evolution.empty:
        st.info("Aucune donnée FAP disponible.")
    else:
        derniere_val_fap = f"{int(df_fap_evolution['nb_cumule'].iloc[-1]):,}".replace(",", "\u202f")
        _help_fap = "Une fiche action pilotable est une action qui comprend au moins un titre, une description, un statut et une personne pilote."
        if selected_region != "Toutes" and selected_departement == "Tous":
            st.markdown(f"Sur la région **{selected_region}**, **{derniere_val_fap} fiches actions pilotables** ont été créées.", help=_help_fap)
        elif selected_region != "Toutes" and selected_departement != "Tous":
            st.markdown(f"Sur le département **{selected_departement}**, **{derniere_val_fap} fiches actions pilotables** ont été créées.", help=_help_fap)
        else:
            st.markdown(f"Sur le **territoire national**, **{derniere_val_fap} fiches actions pilotables** ont été créées.", help=_help_fap)

        fap_data = [
            {
                "id": "Fiches actions pilotables",
                "data": [
                    {"x": row['mois'].strftime('%Y-%m'), "y": int(row['nb_cumule'])}
                    for _, row in df_fap_evolution[df_fap_evolution['mois'] >= DATE_DEBUT_GRAPHES].iterrows()
                ]
            }
        ]

        with elements("area_fap_evolution"):
            with mui.Box(sx={"height": 400}):
                nivo.Line(
                    data=fap_data,
                    margin={"top": 20, "right": 30, "bottom": 50, "left": 60},
                    xScale={"type": "point"},
                    yScale={"type": "linear", "min": 0, "max": "auto", "stacked": False, "reverse": False},
                    curve="monotoneX",
                    axisTop=None,
                    axisRight=None,
                    axisBottom={
                        "tickSize": 5,
                        "tickPadding": 5,
                        "tickRotation": -45,
                        "legend": "",
                        "legendOffset": 45,
                        "legendPosition": "middle"
                    },
                    axisLeft={
                        "tickSize": 5,
                        "tickPadding": 5,
                        "tickRotation": 0,
                    },
                    enableArea=True,
                    areaOpacity=0.3,
                    enablePoints=False,
                    useMesh=True,
                    enableSlices="x",
                    colors=["#f59e0b"],
                    theme=theme_actif,
                )

# --- Histogramme : Répartition des PAP par type ---

df_pap_type = df_pap.copy()
if selected_region != "Toutes":
    df_pap_type = df_pap_type[df_pap_type["region_name"] == selected_region]
if selected_departement != "Tous":
    df_pap_type = df_pap_type[df_pap_type["departement_name"] == selected_departement]

df_pap_type["nom_plan"] = df_pap_type["nom_plan"].str.replace("(incluant Plans qualité de l'air)", "", regex=False).str.strip()

df_pap_type_counts = (
    df_pap_type.groupby("nom_plan")
    .size()
    .reset_index(name="count")
    .sort_values("count", ascending=False)
)

if df_pap_type_counts.empty:
    st.info("Aucune donnée de type de plan d'action disponible.")
else:
    if selected_region != "Toutes" and selected_departement == "Tous":
        _label_type = f"Sur la région **{selected_region}**"
    elif selected_region != "Toutes" and selected_departement != "Tous":
        _label_type = f"Sur le département **{selected_departement}**"
    else:
        _label_type = "Sur le **territoire national**"
    _nb_types = len(df_pap_type_counts)
    st.markdown(f"{_label_type}, il y a **{_nb_types} types de plans** pilotés sur Territoires en Transitions.")

    bar_data_pap_type = [
        {"type": row["nom_plan"], "Nombre": int(row["count"])}
        for _, row in df_pap_type_counts.iterrows()
    ]

    with elements("bar_pap_type"):
        with mui.Box(sx={"height": 500}):
            nivo.Bar(
                data=bar_data_pap_type,
                keys=["Nombre"],
                indexBy="type",
                margin={"top": 20, "right": 30, "bottom": 140, "left": 60},
                padding=0.35,
                valueScale={"type": "linear"},
                indexScale={"type": "band", "round": True},
                colors=["#6366f1"],
                borderRadius=4,
                axisTop=None,
                axisRight=None,
                axisBottom={
                    "tickSize": 5,
                    "tickPadding": 5,
                    "tickRotation": -35,
                    "legend": "",
                    "legendPosition": "middle",
                    "legendOffset": 65,
                },
                axisLeft={
                    "tickSize": 5,
                    "tickPadding": 5,
                    "tickRotation": 0,
                    "legend": "",
                    "legendPosition": "middle",
                    "legendOffset": -50,
                },
                labelSkipWidth=12,
                labelSkipHeight=12,
                labelTextColor={"from": "color", "modifiers": [["darker", 2]]},
                enableLabel=True,
                theme=theme_actif,
            )




# ===================================================
# === Section 5 : indicateurs et OD =================
# ===================================================

st.markdown("---")

if selected_region != "Toutes" and selected_departement == "Tous":
    st.badge(f'Indicateurs & Open Data : **{selected_region}**', icon=":material/task:", color="orange")
elif selected_region != "Toutes" and selected_departement != "Tous":
    st.badge(f'Indicateurs & Open Data : **{selected_departement}**', icon=":material/task:", color="orange")
else:
    st.badge(f'Indicateurs & Open Data : **Territoire national**', icon=":material/task:", color="orange")

df_ind_filtered = df_ind_perso.copy()
df_ind_filtered['mois'] = pd.to_datetime(df_ind_filtered['mois'])
if selected_region != "Toutes":
    df_ind_filtered = df_ind_filtered[df_ind_filtered["region_name"] == selected_region]
if selected_departement != "Tous":
    df_ind_filtered = df_ind_filtered[df_ind_filtered["departement_name"] == selected_departement]

df_ind_evolution = (
    df_ind_filtered.groupby('mois')['nb_ind_perso']
    .sum()
    .reset_index(name='nb')
    .sort_values('mois')
)

if df_ind_evolution.empty:
    st.info("Aucune donnée d'indicateurs disponible pour les filtres sélectionnés.")
else:
    derniere_val_ind = f"{int(df_ind_evolution['nb'].iloc[-1]):,}".replace(",", "\u202f")
    if selected_region != "Toutes" and selected_departement == "Tous":
        st.markdown(f"Sur la région **{selected_region}**, **{derniere_val_ind} indicateurs personnalisés** ont été créés.")
    elif selected_region != "Toutes" and selected_departement != "Tous":
        st.markdown(f"Sur le département **{selected_departement}**, **{derniere_val_ind} indicateurs personnalisés** ont été créés.")
    else:
        st.markdown(f"Sur le **territoire national**, **{derniere_val_ind} indicateurs personnalisés** ont été créés.")

    ind_data = [
        {
            "id": "Indicateurs personnalisés",
            "data": [
                {"x": row['mois'].strftime('%Y-%m'), "y": int(row['nb'])}
                for _, row in df_ind_evolution[df_ind_evolution['mois'] >= DATE_DEBUT_GRAPHES].iterrows()
            ]
        }
    ]

    with elements("area_ind_perso"):
        with mui.Box(sx={"height": 450}):
            nivo.Line(
                data=ind_data,
                margin={"top": 20, "right": 30, "bottom": 50, "left": 70},
                xScale={"type": "point"},
                yScale={"type": "linear", "min": 0, "max": "auto", "stacked": False, "reverse": False},
                curve="monotoneX",
                axisTop=None,
                axisRight=None,
                axisBottom={
                    "tickSize": 5,
                    "tickPadding": 5,
                    "tickRotation": -45,
                    "legend": "",
                    "legendOffset": 45,
                    "legendPosition": "middle"
                },
                axisLeft={
                    "tickSize": 5,
                    "tickPadding": 5,
                    "tickRotation": 0,
                    "legend": "Nb indicateurs",
                    "legendPosition": "middle",
                    "legendOffset": -60,
                },
                enableArea=True,
                areaOpacity=0.3,
                enablePoints=False,
                useMesh=True,
                enableSlices="x",
                colors=["#f97316"],
                theme=theme_actif,
            )

df_ind_od_filtered = df_ind_od.copy()
df_ind_od_filtered['mois'] = pd.to_datetime(df_ind_od_filtered['mois'])
if selected_region != "Toutes":
    df_ind_od_filtered = df_ind_od_filtered[df_ind_od_filtered["region_name"] == selected_region]
if selected_departement != "Tous":
    df_ind_od_filtered = df_ind_od_filtered[df_ind_od_filtered["departement_name"] == selected_departement]

df_ind_od_evolution = (
    df_ind_od_filtered.groupby('mois')['nb_values_od_cum']
    .sum()
    .reset_index(name='nb')
    .sort_values('mois')
)

df_ind_od_producteur_filtered = df_ind_od_producteur.copy()
if selected_region != "Toutes":
    df_ind_od_producteur_filtered = df_ind_od_producteur_filtered[df_ind_od_producteur_filtered["region_name"] == selected_region]
if selected_departement != "Tous":
    df_ind_od_producteur_filtered = df_ind_od_producteur_filtered[df_ind_od_producteur_filtered["departement_name"] == selected_departement]

_nb_titres = df_ind_od_producteur_filtered['titre'].nunique()
_nb_sources = df_ind_od_producteur_filtered['producteur'].nunique()

if df_ind_od_evolution.empty:
    st.info("Aucune donnée d'indicateurs open data disponible pour les filtres sélectionnés.")
else:
    derniere_val_od = f"{int(df_ind_od_evolution['nb'].iloc[-1]):,}".replace(",", "\u202f")
    if selected_region != "Toutes" and selected_departement == "Tous":
        st.markdown(f"Sur la région **{selected_region}**, Territoires en Transitions a mis à disposition **{derniere_val_od} valeurs d'indicateurs en open data**. Ces données englobent **{_nb_titres} indicateurs** provenant de **{_nb_sources} sources**.")
    elif selected_region != "Toutes" and selected_departement != "Tous":
        st.markdown(f"Sur le département **{selected_departement}**, Territoires en Transitions a mis à disposition **{derniere_val_od} valeurs d'indicateurs en open data**. Ces données englobent **{_nb_titres} indicateurs** provenant de **{_nb_sources} sources**.")
    else:
        st.markdown(f"Sur le **territoire national**, Territoires en Transitions a mis à disposition **{derniere_val_od} valeurs d'indicateurs en open data**. Ces données englobent **{_nb_titres} indicateurs** provenant de **{_nb_sources} sources**.")

    ind_od_data = [
        {
            "id": "Valeurs indicateurs open data",
            "data": [
                {"x": row['mois'].strftime('%Y-%m'), "y": int(row['nb'])}
                for _, row in df_ind_od_evolution[df_ind_od_evolution['mois'] >= DATE_DEBUT_GRAPHES].iterrows()
            ]
        }
    ]

    with elements("area_ind_od"):
        with mui.Box(sx={"height": 450}):
            nivo.Line(
                data=ind_od_data,
                margin={"top": 20, "right": 30, "bottom": 50, "left": 70},
                xScale={"type": "point"},
                yScale={"type": "linear", "min": 0, "max": "auto", "stacked": False, "reverse": False},
                curve="monotoneX",
                axisTop=None,
                axisRight=None,
                axisBottom={
                    "tickSize": 5,
                    "tickPadding": 5,
                    "tickRotation": -45,
                    "legend": "",
                    "legendOffset": 45,
                    "legendPosition": "middle"
                },
                axisLeft={
                    "tickSize": 5,
                    "tickPadding": 5,
                    "tickRotation": 0,
                    "legend": "Nb valeurs",
                    "legendPosition": "middle",
                    "legendOffset": -60,
                },
                enableArea=True,
                areaOpacity=0.3,
                enablePoints=False,
                useMesh=True,
                enableSlices="x",
                colors=["#8b5cf6"],
                theme=theme_actif,
            )
