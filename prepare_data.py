import pandas as pd

EXCEL_PATH = "Italia - Copia.xlsx"     # il tuo excel grosso
PARQUET_PATH = "dati_preparati.parquet"

def main():
    print("Carico Excel...")
    df = pd.read_excel(EXCEL_PATH)

    # qui puoi già fare pulizie minime / tipi
    # es: se ci sono colonne data note:
    # df["data_nascita"] = pd.to_datetime(df["data_nascita"], errors="coerce")

    print("Salvo in Parquet...")
    df.to_parquet(PARQUET_PATH, index=False)

    print("Fatto! File salvato come", PARQUET_PATH)

if __name__ == "__main__":
    main()
