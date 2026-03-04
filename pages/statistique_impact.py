import streamlit as st
import pandas as pd
from streamlit_elements import elements, nivo, mui
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta

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


# ===================================================
# DONNÉES : Chargement depuis la base de données
# Les données sont mises en cache pendant 2 jours
# pour éviter des requêtes répétées à chaque interaction.
# ===================================================

@st.cache_resource(ttl="2d")
def load_data():
    df_ct_actives = read_table('ct_actives')
    df_ct_niveau = read_table('ct_niveau')
    df_ct_users_actifs = read_table('user_actifs_ct_mois')
    df_pap_statut_region = read_table('pap_statut_region')
    df_pap_note_region = read_table('pap_note_region')
    return df_ct_actives, df_ct_niveau, df_ct_users_actifs, df_pap_statut_region, df_pap_note_region

df_ct_actives, df_ct_niveau, df_ct_users_actifs, df_pap_statut_region, df_pap_note_region = load_data()


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

st.markdown("*La sélection d'un territoire s'applique à tous les graphes*")

# Badge indiquant le périmètre géographique actif
if selected_region != "Toutes" and selected_departement == "Tous":
    st.badge(f'Activation : **{selected_region}**', icon=":material/trending_up:", color="green")
elif selected_region != "Toutes" and selected_departement != "Tous":
    st.badge(f'Activation : **{selected_departement}**', icon=":material/trending_up:", color="green")
else:
    st.badge(f'Activation : **Territoire national**', icon=":material/trending_up:", color="green")

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
if selected_region == "Toutes" and selected_departement == "Tous":
    st.markdown(f"Sur le **territoire national**, Territoires en Transitions comptabilise **{int(df_ct_actives_selected.shape[0])} collectivités** ayant créé un profil sur la plateforme.")
elif selected_region != "Toutes" and selected_departement == "Tous":
    st.markdown(f"Sur la région **{selected_region}**, Territoires en Transitions comptabilise **{int(df_ct_actives_selected.shape[0])} collectivités** ayant créé un profil sur la plateforme.")
elif selected_region != "Toutes" and selected_departement != "Tous":
    st.markdown(f"Sur le département **{selected_departement}**, Territoires en Transitions comptabilise **{int(df_ct_actives_selected.shape[0])} collectivités** ayant créé un profil sur la plateforme.")

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
                    "legend": "Mois",
                    "legendOffset": 45,
                    "legendPosition": "middle"
                },
                axisLeft={
                    "tickSize": 5,
                    "tickPadding": 5,
                    "tickRotation": 0,
                    "legend": "Nombre cumulé",
                    "legendOffset": -50,
                    "legendPosition": "middle"
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
