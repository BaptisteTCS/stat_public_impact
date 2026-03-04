import os
from typing import Optional, Sequence, Mapping, Any

import pandas as pd
from sqlalchemy import create_engine, text

try:
    # streamlit is available at runtime; used for secrets and caching
    import streamlit as st
except Exception:  # pragma: no cover - allow import without streamlit context
    st = None  # type: ignore


def _get_database_url(secret_key: str = "DATABASE_URL") -> str:
    """Return database URL from Streamlit secrets or environment variable.

    Parameters:
    - secret_key: name of the secret key to use (default: "DATABASE_URL")

    Order of precedence:
    1) st.secrets[secret_key] if available
    2) os.environ[secret_key]
    """
    # Prefer Streamlit secrets when available
    if st is not None:
        try:
            secret_val = st.secrets.get(secret_key)  # type: ignore[attr-defined]
            if secret_val:
                return str(secret_val)
        except Exception:
            # secrets might not be configured in local dev
            pass

    env_val = os.getenv(secret_key)
    if not env_val:
        raise RuntimeError(
            f"{secret_key} non défini. Configurez .streamlit/secrets.toml ou la variable d'environnement."
        )
    return env_val


def _create_sqlalchemy_engine(secret_key: str = "DATABASE_URL"):
    db_url = _get_database_url(secret_key)
    # Normalise pour utiliser psycopg3 si l'URL n'indique pas de driver explicitement
    if db_url.startswith("postgresql://") and "+" not in db_url.split("://", 1)[0]:
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
    # Let SQLAlchemy/psycopg handle pooling defaults; Neon recommends many short-lived connections
    engine = create_engine(db_url, pool_pre_ping=True, pool_recycle=300)
    return engine


if st is not None:
    # Cache the engine across reruns in Streamlit
    @st.cache_resource(show_spinner=False)
    def get_engine():
        return _create_sqlalchemy_engine()
    
    @st.cache_resource(show_spinner=False)
    def get_engine_prod():
        return _create_sqlalchemy_engine("database_prod")
    
    @st.cache_resource(show_spinner=False)
    def get_engine_prod_writing():
        return _create_sqlalchemy_engine("database_prod_writing")
    
    @st.cache_resource(show_spinner=False)
    def get_engine_pre_prod():
        return _create_sqlalchemy_engine("database_pre_prod")
else:  # pragma: no cover
    _ENGINE = None
    _ENGINE_PROD = None
    _ENGINE_PROD_WRITING = None
    _ENGINE_PRE_PROD = None

    def get_engine():  # type: ignore
        global _ENGINE
        if _ENGINE is None:
            _ENGINE = _create_sqlalchemy_engine()
        return _ENGINE
    
    def get_engine_prod():  # type: ignore
        global _ENGINE_PROD
        if _ENGINE_PROD is None:
            _ENGINE_PROD = _create_sqlalchemy_engine("database_prod")
        return _ENGINE_PROD
    
    def get_engine_prod_writing():  # type: ignore
        global _ENGINE_PROD_WRITING
        if _ENGINE_PROD_WRITING is None:
            _ENGINE_PROD_WRITING = _create_sqlalchemy_engine("database_prod_writing")
        return _ENGINE_PROD_WRITING
    
    def get_engine_pre_prod():  # type: ignore
        global _ENGINE_PRE_PROD
        if _ENGINE_PRE_PROD is None:
            _ENGINE_PRE_PROD = _create_sqlalchemy_engine("database_pre_prod")
        return _ENGINE_PRE_PROD


def read_table(
    table_name: str,
    *,
    schema: Optional[str] = None,
    columns: Optional[Sequence[str]] = None,
    where_sql: Optional[str] = None,
    params: Optional[Mapping[str, Any]] = None,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """Read a full table (or subset) into a pandas DataFrame.

    Parameters
    - table_name: required table name (e.g. "pap_date_passage")
    - schema: optional schema (e.g. "public"). If None, relies on DB defaults
    - columns: optional list of columns to select
    - where_sql: optional SQL conditions (e.g. "created_at >= :d")
    - params: parameters to bind in where_sql
    - limit: optional LIMIT
    """
    if not table_name:
        raise ValueError("table_name est requis")

    q_cols = "*" if not columns else ", ".join([f'"{c}"' for c in columns])
    if schema:
        qualified = f'"{schema}"."{table_name}"'
    else:
        qualified = f'"{table_name}"'

    sql_parts = [f"SELECT {q_cols} FROM {qualified}"]
    if where_sql:
        sql_parts.append(f"WHERE {where_sql}")
    if limit is not None:
        sql_parts.append(f"LIMIT {int(limit)}")

    sql_query = "\n".join(sql_parts)

    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql_query(text(sql_query), conn, params=dict(params or {}))
    return df


