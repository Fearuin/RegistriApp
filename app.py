import streamlit as st
import pandas as pd
import numpy as np

# ==========================
# CONFIGURAZIONE
# ==========================
st.set_page_config(layout="wide")

# Percorso del file Parquet già preparato
DATA_PATH = "dati_preparati.parquet"

# Nomi colonne nel dataset
BIRTH_PROV_COL = "Prov. Nascita"  # colonna con EE (nati estero)
REGION_COL = "Regione"
PROV_COL = "Provincia"
COMUNE_COL = "Comune"

# Colonne "di nascita" da ignorare nei filtri generici
IGNORA_COLONNE_NASCITA = {
    "Regione di nascita",
    "Prov. Nascita",
    "Comune di nascita",
}


# ==========================
# FUNZIONI DI SUPPORTO
# ==========================
def detect_column_type(series: pd.Series) -> str:
    """Riconosce se una colonna è numerica, data o testo."""
    series_no_na = series.dropna()

    # 1) Provo come numerico
    try:
        pd.to_numeric(series_no_na)
        return "numeric"
    except Exception:
        pass

    # 2) Provo come data
    try:
        parsed = pd.to_datetime(
            series_no_na, errors="raise", infer_datetime_format=True
        )
        if parsed.notna().mean() > 0.8:
            return "date"
    except Exception:
        pass

    # 3) Default → testo
    return "text"


def is_integer_numeric(series: pd.Series) -> bool:
    """Ritorna True se tutti i valori numerici sono interi."""
    s = pd.to_numeric(series.dropna(), errors="coerce").dropna()
    if s.empty:
        return True
    return (s % 1 == 0).all()


@st.cache_data
def load_data_and_types():
    """
    Carica il dataset dal Parquet e calcola:
    - tipi di colonna (numeric / date / text)
    - tipo numerico (int/float)
    Tutto viene cachato per evitare ricalcoli.
    """
    df = pd.read_parquet(DATA_PATH)

    column_types = {}
    numeric_kinds = {}

    for col in df.columns:
        col_type = detect_column_type(df[col])
        column_types[col] = col_type

        if col_type == "numeric":
            numeric_kinds[col] = "int" if is_integer_numeric(df[col]) else "float"

        if col_type == "date":
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return df, column_types, numeric_kinds


# ==========================
# INTERFACCIA
# ==========================
st.title("Data Explorer Dinamico")

st.write(
    "Questo tool carica un dataset pre-caricato sul server, rileva i tipi di colonna "
    "e ti permette di filtrare in modo dinamico e veloce. "
    "Include un filtro per nati in Italia / estero (EE) e filtri a cascata "
    "**Regione → Provincia → Comune**."
)

# Carico i dati e i tipi (con cache)
try:
    df_originale, column_types, numeric_kinds = load_data_and_types()
except FileNotFoundError:
    st.error(
        f"File Parquet non trovato: `{DATA_PATH}`. "
        "Assicurati di averlo generato prima (es. convertendo l'Excel)."
    )
    st.stop()

st.sidebar.header("Filtri")

# ==========================
# FILTRO SPECIFICO: ITALIA / ESTERO (EE) SU "Provincia di nascita"
# ==========================
df_lavoro = df_originale.copy()

if BIRTH_PROV_COL in df_lavoro.columns:
    st.sidebar.subheader("Filtro nascita Italia / Estero")

    nascita_filter = st.sidebar.radio(
        "Seleziona gruppo",
        options=[
            "Tutti",
            "Solo nati in Italia (no EE)",
            "Solo nati all'estero (EE)",
        ],
        index=0,
    )

    birth_series = df_lavoro[BIRTH_PROV_COL].astype(str).str.upper()

    if nascita_filter == "Solo nati in Italia (no EE)":
        df_lavoro = df_lavoro[birth_series != "EE"]
    elif nascita_filter == "Solo nati all'estero (EE)":
        df_lavoro = df_lavoro[birth_series == "EE"]

    st.sidebar.caption(f"Righe dopo filtro Italia/Estero: {len(df_lavoro)}")
else:
    st.sidebar.warning(
        f"Colonna '{BIRTH_PROV_COL}' non trovata. "
        "Il filtro Italia/Estero è disabilitato."
    )

st.subheader("Prime righe del dataset (dopo eventuale filtro Italia/Estero)")
st.dataframe(df_lavoro.head(), use_container_width=True)

with st.expander("Mostra tipi di colonna rilevati"):
    st.json(column_types)
    st.write("Tipologia numerica (int/float):", numeric_kinds)


# ==========================
# FILTRI DINAMICI
# ==========================
st.sidebar.subheader("Filtri dinamici")

filters: dict[str, object] = {}

# ---- Filtri a cascata Regione → Provincia → Comune ----
selected_regions = None
selected_provs = None
selected_comuni = None

# 1) Regione (non viene mai aggiornata automaticamente dagli altri)
if REGION_COL in df_lavoro.columns:
    reg_vals = sorted(df_lavoro[REGION_COL].dropna().unique())
    selected_regions = st.sidebar.multiselect("Regione", options=reg_vals)
    filters[REGION_COL] = selected_regions

# 2) Provincia (opzioni filtrate in base alla Regione selezionata)
if PROV_COL in df_lavoro.columns:
    prov_base = df_lavoro
    if selected_regions:
        prov_base = prov_base[prov_base[REGION_COL].isin(selected_regions)]
    prov_vals = sorted(prov_base[PROV_COL].dropna().unique())
    selected_provs = st.sidebar.multiselect("Provincia", options=prov_vals)
    filters[PROV_COL] = selected_provs

# 3) Comune (opzioni filtrate in base a Provincia, altrimenti Regione)
if COMUNE_COL in df_lavoro.columns:
    comune_base = df_lavoro
    if selected_provs:
        comune_base = comune_base[comune_base[PROV_COL].isin(selected_provs)]
    elif selected_regions:
        comune_base = comune_base[comune_base[REGION_COL].isin(selected_regions)]
    comune_vals = sorted(comune_base[COMUNE_COL].dropna().unique())
    selected_comuni = st.sidebar.multiselect("Comune", options=comune_vals)
    filters[COMUNE_COL] = selected_comuni

# ---- Altri filtri generati automaticamente ----
for col, col_type in column_types.items():
    # Salto le colonne gestite a mano e le colonne "di nascita" da ignorare
    if col in (REGION_COL, PROV_COL, COMUNE_COL):
        continue
    if col in IGNORA_COLONNE_NASCITA:
        continue

    st.sidebar.markdown(f"**{col}**")

    col_data = df_lavoro[col]

    if col_type == "numeric":
        s = pd.to_numeric(col_data, errors="coerce").dropna()
        if s.empty:
            st.sidebar.info(f"Nessun valore numerico valido in '{col}'.")
            filters[col] = None
            continue

        is_int = numeric_kinds.get(col) == "int"

        if is_int:
            min_val = int(s.min())
            max_val = int(s.max())

            if min_val == max_val:
                st.sidebar.info(
                    f"Tutti i valori di '{col}' sono {min_val}. Nessun filtro necessario."
                )
                filters[col] = (min_val, max_val)
            else:
                selected_range = st.sidebar.slider(
                    f"Intervallo (int) per {col}",
                    min_value=min_val,
                    max_value=max_val,
                    value=(min_val, max_val),
                    step=1,
                )
                filters[col] = selected_range
        else:
            min_val = float(s.min())
            max_val = float(s.max())

            if min_val == max_val:
                st.sidebar.info(
                    f"Tutti i valori di '{col}' sono {min_val}. Nessun filtro necessario."
                )
                filters[col] = (min_val, max_val)
            else:
                selected_range = st.sidebar.slider(
                    f"Intervallo (float) per {col}",
                    min_value=min_val,
                    max_value=max_val,
                    value=(min_val, max_val),
                )
                filters[col] = selected_range

    elif col_type == "date":
        col_dt = pd.to_datetime(col_data, errors="coerce")
        min_date, max_date = col_dt.min(), col_dt.max()

        if pd.isna(min_date) or pd.isna(max_date):
            st.sidebar.warning(
                f"Impossibile determinare un intervallo di date valido per '{col}'."
            )
            filters[col] = None
        else:
            default_start = min_date.date()
            default_end = max_date.date()
            selected_dates = st.sidebar.date_input(
                f"Intervallo date per {col}",
                (default_start, default_end),
            )
            filters[col] = selected_dates

    else:  # text generico
        unique_vals = col_data.dropna().unique()
        unique_vals = sorted(unique_vals)
        selected_vals = st.sidebar.multiselect(
            f"Valori per {col}",
            options=unique_vals,
        )
        filters[col] = selected_vals


# ==========================
# APPLICAZIONE FILTRI
# ==========================
st.subheader("Risultato filtrato")

filtered_df = df_lavoro.copy()

for col, col_type in column_types.items():
    f = filters.get(col, None)
    if f is None:
        continue

    if col_type == "numeric":
        min_val, max_val = f
        s = pd.to_numeric(filtered_df[col], errors="coerce")
        mask = (s >= min_val) & (s <= max_val)
        filtered_df = filtered_df[mask]

    elif col_type == "date":
        date_range = f
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_date, end_date = date_range
            col_dt = pd.to_datetime(filtered_df[col], errors="coerce")
            mask = (
                col_dt >= pd.to_datetime(start_date)
            ) & (col_dt <= pd.to_datetime(end_date))
            filtered_df = filtered_df[mask]

    else:  # text (incluse Regione/Provincia/Comune)
        selected_vals = f
        if selected_vals:
            filtered_df = filtered_df[filtered_df[col].isin(selected_vals)]

st.write(f"Totale righe dopo tutti i filtri: **{len(filtered_df)}**")


# ==========================
# TABELLA RISULTATI + DOWNLOAD
# ==========================
st.markdown("---")
st.subheader("Tabella risultati")

enable_edit = st.toggle("Abilita modifica tabella")

column_config = {}

if enable_edit:
    edited_df = st.data_editor(
        filtered_df,
        use_container_width=True,
        column_config=column_config,
        num_rows="dynamic",
    )
    df_to_download = edited_df
else:
    st.dataframe(filtered_df, use_container_width=True)
    df_to_download = filtered_df

st.download_button(
    label="Scarica CSV filtrato",
    data=df_to_download.to_csv(index=False).encode("utf-8"),
    file_name="risultato_filtrato.csv",
    mime="text/csv",
)
