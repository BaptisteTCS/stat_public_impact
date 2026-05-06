import streamlit as st

st.set_page_config(
    page_title="Dashboard TET",
    page_icon="🏄‍♂️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
        [data-testid="collapsedControl"] { display: none; }
        section[data-testid="stSidebar"] { display: none; }
        .block-container { padding-left: 2rem; padding-right: 2rem; max-width: 100%; }
    </style>
""", unsafe_allow_html=True)

pages = {
    "Favoris": [
        st.Page("pages/statistique_impact.py", icon="🌠", default=True),
        st.Page("pages/matrice_impact.py", icon="🎯", url_path="matrice_impact"),
    ],
}

pg = st.navigation(pages, position="hidden")
pg.run()