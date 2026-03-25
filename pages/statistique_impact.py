import os

import streamlit as st
import numpy as np
import pandas as pd
import geopandas as gpd
import plotly.express as px
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


def graph_title(text):
    st.caption(text)


def geo_badge(selected_region, selected_departement, text, icon, color):
    if selected_region != "Toutes" and selected_departement != "Tous":
        label = selected_departement
    elif selected_region != "Toutes":
        label = selected_region
    else:
        label = "Territoire national"
    st.badge(f'{text} : **{label}**', icon=icon, color=color)


# ===================================================
# DONNÉES : Chargement depuis la base de données
# Les données sont mises en cache pendant 2 jours
# pour éviter des requêtes répétées à chaque interaction.
# ===================================================

@st.cache_resource(ttl="2d")
def load_data():
    df_collectivite = read_table('collectivite', where_sql="type_collectivite='EPCI' and nature_collectivite not in ('POLEM', 'PETR', 'SIVU', 'SIVOM', 'SMF', 'SMO')")
    df_ct_actives = read_table('ct_actives') #https://datalore.jetbrains.com/notebook/3z8wdKwizolR7wA321R4Rl/zDBnbKbrbzhC1RYZAKnhxB/ - Date activation
    df_ct_users_actifs = read_table('user_actifs_ct_mois') #https://datalore.jetbrains.com/notebook/3z8wdKwizolR7wA321R4Rl/zDBnbKbrbzhC1RYZAKnhxB/ - User actifs
    df_activite_semaine = read_table('activite_semaine') #https://datalore.jetbrains.com/notebook/3z8wdKwizolR7wA321R4Rl/Dz9DmMwquBQiWTJN0JKlCn/ - L-2
    df_pap = read_table('passage_pap_region')
    df_fap = read_table('evolution_fa_region')
    df_ind_perso = read_table('evolution_ind_pers')
    df_ind_od = read_table('evolution_ind_od')
    df_ind_od_producteur = read_table('ind_od_producteur_indicateur')
    df_labellisation = read_table('labellisation_region')
    df_completude = read_table('completude_region') #https://datalore.jetbrains.com/notebook/3z8wdKwizolR7wA321R4Rl/zDBnbKbrbzhC1RYZAKnhxB/ - Completude region
    df_plans_distrib = read_table('plan_distrib')
    return df_ct_actives, df_ct_users_actifs, df_fap, df_pap, df_ind_perso, df_ind_od, df_ind_od_producteur, df_labellisation, df_collectivite, df_activite_semaine, df_completude, df_plans_distrib

df_ct_actives, df_ct_users_actifs, df_fap, df_pap, df_ind_perso, df_ind_od, df_ind_od_producteur, df_labellisation, df_collectivite, df_activite_semaine, df_completude, df_plans_distrib = load_data()

df_collectivite = df_collectivite[
    ~df_collectivite['nom'].str.contains('SM|PETR|Syndicat', case=False, na=False)
]

df_ct_users_actifs = df_ct_users_actifs[df_ct_users_actifs.email.isin(df_activite_semaine.email.to_list())].copy()


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

st.markdown("## Déployer la transition écologique sur la totalité du territoire.")

# Application des filtres géographiques sur le dataframe principal
df_ct_actives_selected = df_ct_actives.copy()
if selected_region != "Toutes":
    df_ct_actives_selected = df_ct_actives_selected[df_ct_actives_selected["region_name"] == selected_region]
if selected_departement != "Tous":
    df_ct_actives_selected = df_ct_actives_selected[df_ct_actives_selected["departement_name"] == selected_departement]

# Conversion de la date d'activation en datetime sans timezone
df_ct_actives_selected["date_activation"] = pd.to_datetime(
    df_ct_actives_selected["date_activation"],
    errors='coerce',
    utc=False
).dt.tz_localize(None)

# Filtrage : collectivités actives sur les 24 derniers mois
_now = pd.Timestamp.now().normalize()
_date_24m = _now - pd.DateOffset(months=24)

df_users_actifs_geo = df_ct_users_actifs.copy()
df_users_actifs_geo['mois'] = pd.to_datetime(df_users_actifs_geo['mois'])
if selected_region != "Toutes":
    df_users_actifs_geo = df_users_actifs_geo[df_users_actifs_geo["region_name"] == selected_region]
if selected_departement != "Tous":
    df_users_actifs_geo = df_users_actifs_geo[df_users_actifs_geo["departement_name"] == selected_departement]

ids_actifs_24m = set(
    df_users_actifs_geo[df_users_actifs_geo['mois'] >= _date_24m]['collectivite_id'].unique()
)

df_ct_actives_graphe = df_ct_actives_selected[
    df_ct_actives_selected['collectivite_id'].isin(ids_actifs_24m)
].copy()

# Ordre d'affichage souhaité pour les catégories
ordre_prioritaire = ["EPCI", "Communes", "Syndicats", "Communes"]

cats = sorted(
    df_ct_actives_graphe["categorie"].dropna().unique(),
    key=lambda c: ordre_prioritaire.index(c)
    if c in ordre_prioritaire
    else len(ordre_prioritaire)
)

# --- Affichage des métriques : Total global + détail par catégorie ---

# Ligne du total global (affiché en premier, seul sur sa ligne)
_nb_ct = f"{int(df_ct_actives_graphe.shape[0]):,}".replace(",", "\u202f")
if selected_region == "Toutes" and selected_departement == "Tous":
    st.markdown(f"Sur le **territoire national**, **{_nb_ct} collectivités** ont créé un compte sur Territoires en Transitions avec au moins une connexion sur les 24 derniers mois.", help="Les statistiques suivantes présentent le nombre de collectivités ayant créé un compte sur la plateforme. Une collectivité est considérée comme ayant créé un compte lorsqu’au moins une personne utilisatrice active est rattachée à cette collectivité sur la plateforme.")
elif selected_region != "Toutes" and selected_departement == "Tous":
    st.markdown(f"En région **{selected_region}**, **{_nb_ct} collectivités** ont créé un compte sur Territoires en Transitions avec au moins une connexion sur les 24 derniers mois.", help="Les statistiques suivantes présentent le nombre de collectivités ayant créé un compte sur la plateforme. Une collectivité est considérée comme ayant créé un compte lorsqu’au moins une personne utilisatrice active est rattachée à cette collectivité sur la plateforme.")
elif selected_region != "Toutes" and selected_departement != "Tous":
    st.markdown(f"En **{selected_departement}**, **{_nb_ct} collectivités** ont créé un compte sur Territoires en Transitions avec au moins une connexion sur les 24 derniers mois.", help="Les statistiques suivantes présentent le nombre de collectivités ayant créé un compte sur la plateforme. Une collectivité est considérée comme ayant créé un compte lorsqu’au moins une personne utilisatrice active est rattachée à cette collectivité sur la plateforme.")

# Badge indiquant le périmètre géographique actif
geo_badge(selected_region, selected_departement, "Nombre de collectivités ayant créé un compte sur la plateforme", icon=":material/trending_up:", color="green")

# Lignes du détail par catégorie (max 6 colonnes par ligne)
max_cols = 6
for row_start in range(0, len(cats), max_cols):
    row_cats = cats[row_start:row_start + max_cols]
    cols = st.columns(len(row_cats))

    for col, cat in zip(cols, row_cats):
        with col:
            df_cat = df_ct_actives_graphe[df_ct_actives_graphe["categorie"] == cat]
            st.metric(cat, int(df_cat.shape[0]))

# ===================================================
# SECTION 2 : Évolution cumulée des collectivités par catégorie
# Graphique en aires empilées montrant la progression
# mensuelle du nombre de collectivités activées.
# ===================================================

_date_3y = _now - pd.DateOffset(years=3)

# Calcul du nombre cumulé d'activations par mois et par catégorie
df_ct_actives_graphe['mois'] = df_ct_actives_graphe['date_activation'].dt.to_period('M')
df_evolution = df_ct_actives_graphe.groupby(['mois', 'categorie']).size().reset_index(name='nb_ct')
df_evolution['nb_ct_cumule'] = df_evolution.groupby('categorie')['nb_ct'].cumsum()

all_mois = sorted(df_ct_actives_graphe['mois'].dropna().unique())
all_categories = df_ct_actives_graphe['categorie'].dropna().unique()

_period_3y = pd.Period(_date_3y, 'M')

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
    # L'affichage est limité aux 3 dernières années pour la lisibilité.
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
                    for _, row in df_complete[df_complete['mois'] >= _period_3y].iterrows()
                ]
            })

    with elements("area_ct_evolution"):
        with mui.Box(sx={"height": 550}):
            nivo.Line(
                data=area_data_ct_evolution,
                margin={"top": 20, "right": 180, "bottom": 90, "left": 60},
                xScale={"type": "point"},
                yScale={"type": "linear", "min": 0, "max": "auto", "stacked": True, "reverse": False},
                curve="monotoneX",
                axisTop=None,
                axisRight=None,
                axisBottom={
                    "tickSize": 5,
                    "tickPadding": 5,
                    "tickRotation": -45,
                    "legend": "Nombre de collectivités ayant créé un compte sur la plateforme",
                    "legendOffset": 80,
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
# CARTE : Couverture des EPCI sur la plateforme
# Vue filtrée par région/département.
# Périmètre : EPCIs présents dans df_collectivite (filtre nature_insee déjà appliqué en SQL).
# ===================================================

@st.cache_data(show_spinner=False)
def _load_gdf_epci():
    path = os.path.join(os.path.dirname(__file__), '..', 'epcis_2023_collection.json')
    gdf = gpd.read_file(path)
    gdf = gdf.to_crs(epsg=4326)
    gdf["geometry"] = gdf["geometry"].simplify(tolerance=0.001)
    return gdf

gdf_epci = _load_gdf_epci()



# Jointure avec df_collectivite pour enrichir avec region_name / departement_name
gdf_epci['siren'] = gdf_epci['siren'].astype(str).str.strip()
df_collectivite['code_siren_insee'] = df_collectivite['code_siren_insee'].astype(str).str.strip()

gdf_epci = gdf_epci.merge(
    df_collectivite[['code_siren_insee', 'region_name', 'departement_name']].drop_duplicates(),
    left_on='siren', right_on='code_siren_insee', how='inner',
)

# Filtres géographiques
if selected_region != "Toutes":
    gdf_epci = gdf_epci[gdf_epci["region_name"] == selected_region]
if selected_departement != "Tous":
    gdf_epci = gdf_epci[gdf_epci["departement_name"] == selected_departement]

# Déterminer quels EPCI ont un profil TET (filtre 24 mois pour cohérence avec le graphique 1)
_sirens_avec_profil = set(
    df_ct_actives[
        (df_ct_actives['categorie'] == 'EPCI')
        & (df_ct_actives['collectivite_id'].isin(ids_actifs_24m))
    ]['siren'].dropna().astype(str)
) if 'siren' in df_ct_actives.columns else set()

df_pap_geo = df_pap.copy()
if selected_region != "Toutes":
    df_pap_geo = df_pap_geo[df_pap_geo["region_name"] == selected_region]
if selected_departement != "Tous":
    df_pap_geo = df_pap_geo[df_pap_geo["departement_name"] == selected_departement]
_ct_ids_avec_pap = set(df_pap_geo['collectivite_id'].unique()) & ids_actifs_24m

_sirens_avec_pap = set(
    df_ct_actives[
        (df_ct_actives['categorie'] == 'EPCI')
        & (df_ct_actives['collectivite_id'].isin(_ct_ids_avec_pap))
    ]['siren'].dropna().astype(str)
)

_STATUT_PAP = "Compte + Plan d'action pilotable"
_STATUT_PROFIL = "Compte seul"
_STATUT_SANS = "Sans compte"
_STATUT_ORDER = [_STATUT_PAP, _STATUT_PROFIL, _STATUT_SANS]
_COLOR_MAP = {
    _STATUT_PAP:    "#22c55e",
    _STATUT_PROFIL: "#93c5fd",
    _STATUT_SANS:   "#cbd5e1",
}

def _statut_epci(siren):
    if siren in _sirens_avec_pap:
        return _STATUT_PAP
    if siren in _sirens_avec_profil:
        return _STATUT_PROFIL
    return _STATUT_SANS

gdf_epci['statut'] = gdf_epci['siren'].apply(_statut_epci)

if gdf_epci.empty:
    st.info("Aucune donnée EPCI disponible pour la carte.")
else:
    _col_carte, _col_waffle = st.columns([2, 1])

    with _col_carte:

        geo_badge(selected_region, selected_departement, "Carte des EPCI actives", icon=":material/map:", color="green")

        _nb_pap = int((gdf_epci['statut'] == _STATUT_PAP).sum())
        _nb_profil = int((gdf_epci['statut'] == _STATUT_PROFIL).sum())
        _nb_sans = int((gdf_epci['statut'] == _STATUT_SANS).sum())
        _total_carte = _nb_pap + _nb_profil + _nb_sans
        _nb_avec = _nb_pap + _nb_profil
        _pct = round(_nb_avec / _total_carte * 100) if _total_carte else 0
        _total_fmt = f"{_total_carte:,}".replace(",", "\u202f")
        _avec_fmt = f"{_nb_avec:,}".replace(",", "\u202f")
        _pct_pap = round(_nb_pap / _total_carte * 100) if _total_carte else 0

        if selected_region == "Toutes" and selected_departement == "Tous":
            st.markdown(f"Sur le **territoire national**, **{_pct} % des EPCI** ont créé un compte sur Territoires en Transitions ({_avec_fmt} sur {_total_fmt}, hors syndicats).")
        elif selected_region != "Toutes" and selected_departement ==  "Tous":
            st.markdown(f"En région **{selected_region}**, **{_pct} % des EPCI** ont créé un compte sur Territoires en Transitions ({_avec_fmt} sur {_total_fmt}, hors syndicats).")
        elif selected_region != "Toutes" and selected_departement != "Tous":
            st.markdown(f"En **{selected_departement}**, **{_pct} % des EPCI** ont créé un compte sur Territoires en Transitions ({_avec_fmt} sur {_total_fmt}, hors syndicats).")

        
    
        _bounds = gdf_epci.total_bounds  # [minx, miny, maxx, maxy]
        _center = {"lat": (_bounds[1] + _bounds[3]) / 2, "lon": (_bounds[0] + _bounds[2]) / 2}
        _span = max(_bounds[2] - _bounds[0], _bounds[3] - _bounds[1])
        if _span < 1:
            _zoom = 8
        elif _span < 3:
            _zoom = 6.5
        elif _span < 6:
            _zoom = 5.5
        else:
            _zoom = 4.6

        _fig_carte = px.choropleth_mapbox(
            gdf_epci,
            geojson=gdf_epci.geometry,
            locations=gdf_epci.index,
            color='statut',
            color_discrete_map=_COLOR_MAP,
            mapbox_style='carto-positron',
            zoom=_zoom,
            center=_center,
            opacity=0.75,
            hover_name='nom',
            hover_data={'statut': True},
            labels={'statut': ''},
            category_orders={'statut': _STATUT_ORDER},
        )
        _fig_carte.update_traces(marker_line_width=0.3, marker_line_color='white')
        _fig_carte.update_layout(
            margin={"r": 0, "t": 0, "l": 0, "b": 0},
            height=600,
            showlegend=False,
        )
        st.plotly_chart(_fig_carte, use_container_width=True)

    with _col_waffle:
        geo_badge(selected_region, selected_departement, "Progression de l'activation des EPCI", icon=":material/clock_loader_60:", color="green")

        if selected_region == "Toutes" and selected_departement == "Tous":
            st.markdown(f"Sur le **territoire national**, **{_pct_pap} % des EPCI** ont un plan d'action pilotable.", help="Un plan d'action pilotable est un plan contenant au moins 5 fiches avec un titre, un statut et une personne pilote.")
        elif selected_region != "Toutes" and selected_departement ==  "Tous":
            st.markdown(f"En région **{selected_region}**, **{_pct_pap} % des EPCI** ont un plan d'action pilotable.", help="Un plan d'action pilotable est un plan contenant au moins 5 fiches avec un titre, un statut et une personne pilote.")
        elif selected_region != "Toutes" and selected_departement != "Tous":
            st.markdown(f"En **{selected_departement}**, **{_pct_pap} % des EPCI** ont un plan d'action pilotable.", help="Un plan d'action pilotable est un plan contenant au moins 5 fiches avec un titre, un statut et une personne pilote.")


        if _total_carte > 0:
            _nb_pap_fmt = f"{_nb_pap:,}".replace(",", "\u202f")
            _nb_profil_fmt = f"{_nb_profil:,}".replace(",", "\u202f")
            _nb_sans_fmt = f"{_nb_sans:,}".replace(",", "\u202f")

            waffle_data = [
                {"id": _STATUT_PAP, "label": _STATUT_PAP, "value": _nb_pap},
                {"id": _STATUT_PROFIL, "label": _STATUT_PROFIL, "value": _nb_profil},
                {"id": _STATUT_SANS, "label": _STATUT_SANS, "value": _nb_sans},
            ]

            with elements("waffle_epci"):
                with mui.Box(sx={"height": 450}):
                    nivo.Waffle(
                        data=waffle_data,
                        total=_total_carte,
                        rows=10,
                        columns=10,
                        padding=1.5,
                        colors=[_COLOR_MAP[s] for s in _STATUT_ORDER],
                        borderRadius="50px",
                        animate=True,
                        motionStiffness=90,
                        motionDamping=11,
                        legends=[],
                        theme=theme_actif,
                    )

            for _statut, _count_fmt, _color in [
                (_STATUT_PAP, _nb_pap_fmt, _COLOR_MAP[_STATUT_PAP]),
                (_STATUT_PROFIL, _nb_profil_fmt, _COLOR_MAP[_STATUT_PROFIL]),
                (_STATUT_SANS, _nb_sans_fmt, _COLOR_MAP[_STATUT_SANS]),
            ]:
                st.markdown(
                    f'<span style="display:inline-block;width:12px;height:12px;border-radius:2px;'
                    f'background:{_color};margin-right:8px;vertical-align:middle"></span>'
                    f'{_statut} : **{_count_fmt}**',
                    unsafe_allow_html=True,
                )
        else:
            st.info("Aucune donnée EPCI disponible.")


# ===================================================
# SECTION 3 : Évolution de l'activité (glissant 24 mois)
# Graphique en aire montrant le nombre d'utilisateurs ou de collectivités
# uniques ayant été actifs au cours des 24 derniers mois, mois par mois.
# ===================================================
st.markdown("---")

st.markdown("## Outiller les personnes qui font avancer la planification écologique")

geo_badge(selected_region, selected_departement, "Nombre d’utilisateurs actifs", icon=":material/person_check:", color="blue")

# Préparation du dataframe de base avec filtres géographiques
df_users = df_ct_users_actifs.copy()
df_users['mois'] = pd.to_datetime(df_users['mois'])

if selected_region != "Toutes":
    df_users = df_users[df_users["region_name"] == selected_region]
if selected_departement != "Tous":
    df_users = df_users[df_users["departement_name"] == selected_departement]

_ct_ids_graphe = set(df_ct_actives_graphe['collectivite_id'].unique())
df_users = df_users[df_users['collectivite_id'].isin(_ct_ids_graphe)]

df_users = df_users.drop_duplicates(['mois', 'email'])
col_comptage = 'email'
label_serie = "Utilisateurs actifs"
label_texte = "utilisateurs actifs"

mois_list = sorted(df_users['mois'].unique())

out = []
for m in mois_list:
    mask = (df_users['mois'] <= m) & (df_users['mois'] > m - pd.DateOffset(months=24))
    out.append((m, df_users.loc[mask, col_comptage].nunique()))

df_final = pd.DataFrame(out, columns=['mois', 'valeur_24m'])

if df_final.empty:
    st.info("Aucune donnée disponible pour les filtres sélectionnés.")
else:
    derniere_valeur = f"{int(df_final['valeur_24m'].iloc[-1]):,}".replace(",", "\u202f")
    dernier_mois = df_final['mois'].iloc[-1].strftime('%B %Y')

    if selected_region != "Toutes" and selected_departement == "Tous":
        st.markdown(f"En région **{selected_region}**, Territoires en Transitions compte **{derniere_valeur} {label_texte}** sur les 24 derniers mois.")
    elif selected_region != "Toutes" and selected_departement != "Tous":
        st.markdown(f"En **{selected_departement}**, Territoires en Transitions compte **{derniere_valeur} {label_texte}** sur les 24 derniers mois.")
    else:
        st.markdown(f"Sur le **territoire national**, Territoires en Transitions compte **{derniere_valeur} {label_texte}** sur les 24 derniers mois.")

    area_data_users = [
        {
            "id": label_serie,
            "data": [
                {"x": row['mois'].strftime('%Y-%m'), "y": int(row['valeur_24m'])}
                for _, row in df_final[df_final['mois'] >= DATE_DEBUT_GRAPHES].iterrows()
            ]
        }
    ]

    with elements("area_users_evolution"):
        with mui.Box(sx={"height": 550}):
            nivo.Line(
                data=area_data_users,
                margin={"top": 20, "right": 30, "bottom": 90, "left": 60},
                xScale={"type": "point"},
                yScale={"type": "linear", "min": 0, "max": "auto", "stacked": False, "reverse": False},
                curve="monotoneX",
                axisTop=None,
                axisRight=None,
                axisBottom={
                    "tickSize": 5,
                    "tickPadding": 5,
                    "tickRotation": -45,
                    "legend": "Nombre d'utilisateurs actifs",
                    "legendOffset": 80,
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

# --- Distribution du nombre d'utilisateurs actifs par collectivité (24 derniers mois glissants) ---

geo_badge(selected_region, selected_departement, "Nombre d’utilisateurs actifs par collectivité", icon=":material/group:", color="blue")

_dernier_mois_glissant = df_users['mois'].max()
_mask_24m = (
    (df_users['mois'] <= _dernier_mois_glissant) &
    (df_users['mois'] > _dernier_mois_glissant - pd.DateOffset(months=24))
)
df_users_24m = df_users.loc[_mask_24m]

df_distrib = (
    df_users_24m.groupby('collectivite_id')['email']
    .nunique()
    .reset_index(name='nb_users')
)

if not df_distrib.empty:
    _moyenne = int(df_distrib['nb_users'].mean())
    _max = int(df_distrib['nb_users'].max())

    if selected_region != "Toutes" and selected_departement == "Tous":
        _label_distrib = f"En région **{selected_region}**"
    elif selected_region != "Toutes" and selected_departement != "Tous":
        _label_distrib = f"En **{selected_departement}**"
    else:
        _label_distrib = "Sur le **territoire national**"

    st.markdown(
        f"{_label_distrib}, les collectivités comptent en moyenne "
        f"**{_moyenne} utilisateurs actifs** sur les 24 derniers mois, allant jusqu'à **{_max} utilisateurs actifs** ."
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
        with mui.Box(sx={"height": 550}):
            nivo.Bar(
                data=hist_data,
                keys=["Collectivités"],
                indexBy="tranche",
                margin={"top": 20, "right": 30, "bottom": 90, "left": 60},
                padding=0.25,
                valueScale={"type": "linear"},
                indexScale={"type": "band", "round": True},
                colors=["rgba(59, 130, 246, 0.8)"],
                borderRadius=3,
                borderWidth=1,
                borderColor="#3b82f6",
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
                labelTextColor="#ffffff",
                theme=theme_actif,
            )



# ===================================================
# SECTION 4 : Plans d'action et Fiches actions pilotables
# Deux graphiques côte à côte montrant l'évolution cumulée
# des PAP passés et des fiches actions pilotables.
# ===================================================

st.markdown("---")

st.markdown('## Connaître les forces et faiblesses de chaque territoire')

geo_badge(selected_region, selected_departement, "Complétude de l'état des lieux", icon=":material/readiness_score:", color="orange")

df_completude_filtered = df_completude.copy()
if selected_region != "Toutes":
    df_completude_filtered = df_completude_filtered[df_completude_filtered["region_name"] == selected_region]
if selected_departement != "Tous":
    df_completude_filtered = df_completude_filtered[df_completude_filtered["departement_name"] == selected_departement]

_nb_cae_complete = int((df_completude_filtered[df_completude_filtered["referentiel_id"] == "cae"]["completude"] >= 0.99).sum())
_nb_eci_complete = int((df_completude_filtered[df_completude_filtered["referentiel_id"] == "eci"]["completude"] >= 0.99).sum())

_nb_cae_fmt = f"{_nb_cae_complete:,}".replace(",", "\u202f")
_nb_eci_fmt = f"{_nb_eci_complete:,}".replace(",", "\u202f")

if selected_region != "Toutes" and selected_departement == "Tous":
    _label_edl = f"En région **{selected_region}**"
elif selected_region != "Toutes" and selected_departement != "Tous":
    _label_edl = f"En **{selected_departement}**"
else:
    _label_edl = "Sur le **territoire national**"

st.markdown(
    f"{_label_edl}, **{_nb_cae_fmt} collectivités** ont complété l'état des lieux Climat Air Energie à 100 % "
    f"et **{_nb_eci_fmt}** l'état des lieux Economie Circulaire."
)

bar_completude_data = [
    {"referentiel": "Climat Air Énergie", "Collectivités": _nb_cae_complete},
    {"referentiel": "Économie Circulaire", "Collectivités": _nb_eci_complete},
]

with elements("bar_completude_edl"):
    with mui.Box(sx={"height": 550}):
        nivo.Bar(
            data=bar_completude_data,
            keys=["Collectivités"],
            indexBy="referentiel",
            margin={"top": 20, "right": 30, "bottom": 90, "left": 60},
            padding=0.4,
            valueScale={"type": "linear"},
            indexScale={"type": "band", "round": True},
            colors=["rgba(253, 230, 138, 0.8)"],
            borderRadius=4,
            borderWidth=1,
            borderColor="#fde68a",
            axisTop=None,
            axisRight=None,
            axisBottom={
                "tickSize": 5,
                "tickPadding": 5,
                "tickRotation": 0,
                "legend": "Nombre de collectivités avec un état des lieux complété à 100 %",
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
            labelTextColor="#92400e",
            theme=theme_actif,
        )




geo_badge(selected_region, selected_departement, "Labellisation", icon=":material/stack_star:", color="orange")

df_label_filtered = df_labellisation.copy()
if selected_region != "Toutes":
    df_label_filtered = df_label_filtered[df_label_filtered["region_name"] == selected_region]
if selected_departement != "Tous":
    df_label_filtered = df_label_filtered[df_label_filtered["departement_name"] == selected_departement]

# Pour chaque collectivité × référentiel, ne garder que la labellisation la plus récente
df_label_latest = (
    df_label_filtered.sort_values("obtenue_le")
    .groupby(["collectivite_id", "referentiel"], as_index=False)
    .last()
)

_couleurs_etoiles = {
    1: "#fde68a",
    2: "#fbbf24",
    3: "#f59e0b",
    4: "#d97706",
    5: "#92400e",
}

col_cae, col_eci = st.columns(2)

for col_graph, ref_code, ref_label in [
    (col_cae, "cae", "Climat Air Énergie"),
    (col_eci, "eci", "Économie Circulaire"),
]:
    with col_graph:
        df_ref = df_label_latest[df_label_latest["referentiel"] == ref_code]
        df_counts = (
            df_ref.groupby("etoiles")["collectivite_id"]
            .nunique()
            .reset_index(name="nb")
            .sort_values("etoiles")
        )

        if df_counts.empty:
            st.info(f"Aucune labellisation {ref_label} disponible pour les filtres sélectionnés.")
        else:
            _total_ref = int(df_counts["nb"].sum())
            _total_fmt = f"{_total_ref:,}".replace(",", "\u202f")
            _nb_4plus = int(df_counts[df_counts["etoiles"] >= 4]["nb"].sum())
            _nb_4plus_fmt = f"{_nb_4plus:,}".replace(",", "\u202f")
            st.markdown(f"**{ref_label}** : **{_total_fmt} collectivités** labellisées dont **{_nb_4plus_fmt}** avec 4 étoiles ou plus.")

            donut_data = [
                {
                    "id": f"{'⭐' * int(row['etoiles'])}",
                    "label": f"{int(row['etoiles'])} étoile{'s' if row['etoiles'] > 1 else ''}",
                    "value": int(row["nb"]),
                    "color": _couleurs_etoiles.get(int(row["etoiles"]), "#e5e7eb"),
                }
                for _, row in df_counts.iterrows()
            ]

            with elements(f"donut_label_{ref_code}"):
                with mui.Box(sx={"height": 450}):
                    nivo.Pie(
                        data=donut_data,
                        margin={"top": 30, "right": 120, "bottom": 30, "left": 120},
                        innerRadius=0.55,
                        padAngle=1.5,
                        cornerRadius=4,
                        activeOuterRadiusOffset=8,
                        colors={"datum": "data.color"},
                        arcLinkLabelsSkipAngle=10,
                        arcLinkLabelsTextColor="#31333F",
                        arcLinkLabelsThickness=2,
                        arcLinkLabelsColor={"from": "color"},
                        arcLabelsSkipAngle=15,
                        arcLabelsTextColor={"from": "color", "modifiers": [["darker", 2]]},
                        legends=[],
                        theme=theme_actif,
                    )






st.markdown('---')

st.markdown('## Planifier et prioriser les actions en faveur de la transition écologique')

geo_badge(selected_region, selected_departement, "Plans d'actions sur Territoires en Transitions", icon=":material/globe_book:", color="green")

df_plans_distrib_filtered = df_plans_distrib.copy()
if selected_region != "Toutes":
    df_plans_distrib_filtered = df_plans_distrib_filtered[df_plans_distrib_filtered["region_name"] == selected_region]
if selected_departement != "Tous":
    df_plans_distrib_filtered = df_plans_distrib_filtered[df_plans_distrib_filtered["departement_name"] == selected_departement]

_nb_plans_total = len(df_plans_distrib_filtered)
_nb_plans_actifs = int(df_plans_distrib_filtered["actif_12_mois"].sum())
_nb_plans_score = int(df_plans_distrib_filtered["score_sup_5"].sum())

_nb_plans_total_fmt = f"{_nb_plans_total:,}".replace(",", "\u202f")
_nb_plans_actifs_fmt = f"{_nb_plans_actifs:,}".replace(",", "\u202f")
_nb_plans_score_fmt = f"{_nb_plans_score:,}".replace(",", "\u202f")

if selected_region != "Toutes" and selected_departement == "Tous":
    _label_plans = f"En région **{selected_region}**"
elif selected_region != "Toutes" and selected_departement != "Tous":
    _label_plans = f"En **{selected_departement}**"
else:
    _label_plans = "Sur le **territoire national**"

st.markdown(
    f"{_label_plans}, **{_nb_plans_total_fmt} plans d'actions** ont été créés sur Territoires en Transitions, "
    f"dont **{_nb_plans_actifs_fmt}** plans d'actions pilotables actifs sur les 12 derniers mois "
    f"et **{_nb_plans_score_fmt}** avec une note de qualité supérieure à 5/10."
)

bar_plans_data = [
    {"catégorie": "Plans créés", "Nombre": _nb_plans_total},
    {"catégorie": "Actifs (12 mois)", "Nombre": _nb_plans_actifs},
    {"catégorie": "Qualité > 5/10", "Nombre": _nb_plans_score},
]

with elements("bar_plans_distrib"):
    with mui.Box(sx={"height": 550}):
        nivo.Bar(
            data=bar_plans_data,
            keys=["Nombre"],
            indexBy="catégorie",
            margin={"top": 20, "right": 30, "bottom": 90, "left": 60},
            padding=0.4,
            valueScale={"type": "linear"},
            indexScale={"type": "band", "round": True},
            colors=["#10b981"],
            borderRadius=4,
            borderWidth=1,
            borderColor="#059669",
            axisTop=None,
            axisRight=None,
            axisBottom={
                "tickSize": 5,
                "tickPadding": 5,
                "tickRotation": 0,
                "legend": "Répartition des plans d'actions",
                "legendPosition": "middle",
                "legendOffset": 60,
            },
            axisLeft={
                "tickSize": 5,
                "tickPadding": 5,
                "tickRotation": 0,
                "legend": "Nombre de plans",
                "legendPosition": "middle",
                "legendOffset": -50,
            },
            labelSkipHeight=12,
            enableLabel=True,
            labelTextColor="#ffffff",
            theme=theme_actif,
        )







geo_badge(selected_region, selected_departement, "Plans & Fiches actions", icon=":material/task:", color="blue")

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
        _help_pap = "Un plan d'action pilotable est un plan d'action qui comprend au moins 5 actions pilotables."
        if selected_region != "Toutes" and selected_departement == "Tous":
            st.markdown(f"En région **{selected_region}**, **{derniere_val_pap} plans d'actions pilotables** ont été déposés.", help=_help_pap)
        elif selected_region != "Toutes" and selected_departement != "Tous":
            st.markdown(f"En **{selected_departement}**, **{derniere_val_pap} plans d'actions pilotables** ont été déposés.", help=_help_pap)
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
                    margin={"top": 20, "right": 30, "bottom": 70, "left": 60},
                    xScale={"type": "point"},
                    yScale={"type": "linear", "min": 0, "max": "auto", "stacked": False, "reverse": False},
                    curve="monotoneX",
                    axisTop=None,
                    axisRight=None,
                    axisBottom={
                        "tickSize": 5,
                        "tickPadding": 5,
                        "tickRotation": -45,
                        "legend": "Plans d'action pilotables",
                        "legendOffset": 60,
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
        _help_fap = "Une action pilotable est une action qui comprend au moins un titre, une description, un statut et une personne pilote."
        if selected_region != "Toutes" and selected_departement == "Tous":
            st.markdown(f"En région **{selected_region}**, **{derniere_val_fap} actions pilotables** ont été créées.", help=_help_fap)
        elif selected_region != "Toutes" and selected_departement != "Tous":
            st.markdown(f"En **{selected_departement}**, **{derniere_val_fap} actions pilotables** ont été créées.", help=_help_fap)
        else:
            st.markdown(f"Sur le **territoire national**, **{derniere_val_fap} actions pilotables** ont été créées.", help=_help_fap)

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
                    margin={"top": 20, "right": 30, "bottom": 70, "left": 60},
                    xScale={"type": "point"},
                    yScale={"type": "linear", "min": 0, "max": "auto", "stacked": False, "reverse": False},
                    curve="monotoneX",
                    axisTop=None,
                    axisRight=None,
                    axisBottom={
                        "tickSize": 5,
                        "tickPadding": 5,
                        "tickRotation": -45,
                        "legend": "Fiches actions pilotables",
                        "legendOffset": 60,
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
        _label_type = f"En région **{selected_region}**"
    elif selected_region != "Toutes" and selected_departement != "Tous":
        _label_type = f"En **{selected_departement}**"
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
                colors=["#10b981"],
                borderRadius=4,
                axisTop=None,
                axisRight=None,
                axisBottom={
                    "tickSize": 5,
                    "tickPadding": 5,
                    "tickRotation": -35,
                    "legend": "Répartition des plans par type",
                    "legendPosition": "middle",
                    "legendOffset": 130,
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

geo_badge(selected_region, selected_departement, "Indicateurs & Open Data", icon=":material/task:", color="orange")

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
        st.markdown(f"En région **{selected_region}**, **{derniere_val_ind} indicateurs personnalisés** ont été créés.")
    elif selected_region != "Toutes" and selected_departement != "Tous":
        st.markdown(f"En **{selected_departement}**, **{derniere_val_ind} indicateurs personnalisés** ont été créés.")
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
                margin={"top": 20, "right": 30, "bottom": 70, "left": 70},
                xScale={"type": "point"},
                yScale={"type": "linear", "min": 0, "max": "auto", "stacked": False, "reverse": False},
                curve="monotoneX",
                axisTop=None,
                axisRight=None,
                axisBottom={
                    "tickSize": 5,
                    "tickPadding": 5,
                    "tickRotation": -45,
                    "legend": "Indicateurs personnalisés",
                    "legendOffset": 60,
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
        st.markdown(f"En région **{selected_region}**, Territoires en Transitions a mis à disposition **{derniere_val_od} valeurs d'indicateurs en open data**. Ces données englobent **{_nb_titres} indicateurs** provenant de **{_nb_sources} sources**.")
    elif selected_region != "Toutes" and selected_departement != "Tous":
        st.markdown(f"En **{selected_departement}**, Territoires en Transitions a mis à disposition **{derniere_val_od} valeurs d'indicateurs en open data**. Ces données englobent **{_nb_titres} indicateurs** provenant de **{_nb_sources} sources**.")
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
                margin={"top": 20, "right": 30, "bottom": 70, "left": 70},
                xScale={"type": "point"},
                yScale={"type": "linear", "min": 0, "max": "auto", "stacked": False, "reverse": False},
                curve="monotoneX",
                axisTop=None,
                axisRight=None,
                axisBottom={
                    "tickSize": 5,
                    "tickPadding": 5,
                    "tickRotation": -45,
                    "legend": "Valeurs d'indicateurs en open data",
                    "legendOffset": 60,
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


# ===================================================
# === Section 6 : Labellisation ===================
# ===================================================

st.markdown("---")
