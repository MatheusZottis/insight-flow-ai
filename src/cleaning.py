"""
cleaning.py
Lê a base suja (data/raw/vendas_raw.csv), limpa, padroniza e cria colunas
derivadas. Salva a base limpa em data/processed/ e imprime um relatório.

Uso (na raiz do projeto):
    python src/cleaning.py
"""

import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = ROOT / "data" / "raw" / "vendas_raw.csv"
OUT_DIR = ROOT / "data" / "processed"

REGIONS = {
    "SP": "Sudeste", "RJ": "Sudeste", "MG": "Sudeste", "ES": "Sudeste",
    "PR": "Sul", "SC": "Sul", "RS": "Sul",
    "BA": "Nordeste", "PE": "Nordeste", "CE": "Nordeste",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste",
    "PA": "Norte", "AM": "Norte",
}
STATE_NAMES = {
    "são paulo": "SP", "sao paulo": "SP",
    "rio de janeiro": "RJ",
    "minas gerais": "MG",
}
NAO_INFORMADO = "Não informado"


# ----------------------------------------------------------------------
# Funções auxiliares
# ----------------------------------------------------------------------
def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def parse_date(value):
    """Aceita 2024-05-10, 10/05/2024 e 10-05-2024."""
    if pd.isna(value):
        return pd.NaT
    s = str(value).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return pd.to_datetime(s[:10], format="%Y-%m-%d", errors="coerce")
    if "/" in s:
        return pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
    return pd.to_datetime(s, format="%d-%m-%Y", errors="coerce")


def parse_price(value):
    """Converte 1299.9, 'R$ 1.299,90' e similares para float."""
    if pd.isna(value):
        return np.nan
    s = str(value).strip()
    if "R$" in s or "," in s:
        s = s.replace("R$", "").strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return np.nan


def fill_from_group(df, group_col, target_col):
    """Preenche nulos usando outras linhas do mesmo grupo (ex.: mesmo cliente)."""
    def first_valid(s):
        valid = s.dropna()
        return valid.iloc[0] if len(valid) else np.nan

    fill = df.groupby(group_col)[target_col].transform(first_valid)
    return df[target_col].fillna(fill)


# ----------------------------------------------------------------------
# Pipeline de limpeza
# ----------------------------------------------------------------------
def clean(df: pd.DataFrame):
    report = {}
    report["linhas_originais"] = len(df)

    # 1. Duplicatas exatas
    before = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    report["duplicatas_removidas"] = before - len(df)

    # 2. Datas em formatos mistos
    df["order_date"] = df["order_date"].apply(parse_date)
    report["datas_invalidas"] = int(df["order_date"].isna().sum())
    df = df.dropna(subset=["order_date"])

    # 3. Preço como texto -> número
    textuais = df["unit_price"].astype(str).str.contains("R\\$", regex=True).sum()
    df["unit_price"] = df["unit_price"].apply(parse_price)
    report["precos_convertidos_de_texto"] = int(textuais)
    df = df.dropna(subset=["unit_price"])

    # 4. Categorias: agrupa variações (maiúsculas, espaços, acentos)
    df["category"] = df["category"].astype(str).str.strip()
    key = df["category"].apply(lambda x: strip_accents(x).lower())
    # a forma canônica é a variante mais frequente de cada chave
    canonical = (
        df.assign(_key=key)
        .groupby("_key")["category"]
        .agg(lambda s: s.value_counts().index[0])
    )
    padronizadas = int((df["category"] != key.map(canonical)).sum())
    df["category"] = key.map(canonical)
    report["categorias_padronizadas"] = padronizadas

    # 5. Estados: sigla maiúscula
    def norm_state(s):
        if pd.isna(s):
            return np.nan
        s = str(s).strip()
        return STATE_NAMES.get(s.lower(), s.upper())

    antes = df["state"].copy()
    df["state"] = df["state"].apply(norm_state)
    report["estados_padronizados"] = int((antes != df["state"]).sum())

    # 6. Nulos
    nulos_antes = df.isna().sum()
    report["nulos_antes"] = {k: int(v) for k, v in nulos_antes.items() if v > 0}

    # 6.1 dados do cliente: recupera de outras compras do mesmo cliente
    for col in ["email", "city"]:
        df[col] = fill_from_group(df, "customer_id", col)
    df["city"] = df["city"].fillna(NAO_INFORMADO)
    # e-mail ausente continua nulo (não dá para inventar), mas fica sinalizado
    df["email"] = df["email"].fillna(NAO_INFORMADO)

    # 6.2 dados do pedido: recupera de outros itens do mesmo pedido
    for col in ["channel", "payment_method", "discount_pct"]:
        df[col] = fill_from_group(df, "order_id", col)
    df["channel"] = df["channel"].fillna(NAO_INFORMADO)
    df["payment_method"] = df["payment_method"].fillna(NAO_INFORMADO)
    df["discount_pct"] = df["discount_pct"].fillna(0)

    # 7. Outliers de quantidade (erros de digitação)
    outliers = df["quantity"] > 20
    report["quantidades_outlier_corrigidas"] = int(outliers.sum())
    df.loc[outliers, "quantity"] = 1

    # 8. Tipos corretos
    df["quantity"] = df["quantity"].astype(int)
    df["discount_pct"] = df["discount_pct"].astype(float)

    # 9. Colunas derivadas (base dos indicadores)
    df["gross_revenue"] = (df["quantity"] * df["unit_price"]).round(2)
    df["discount_value"] = (df["gross_revenue"] * df["discount_pct"] / 100).round(2)
    df["net_revenue"] = (df["gross_revenue"] - df["discount_value"]).round(2)
    df["total_cost"] = (df["quantity"] * df["unit_cost"]).round(2)
    df["profit"] = (df["net_revenue"] - df["total_cost"]).round(2)
    df["region"] = df["state"].map(REGIONS).fillna(NAO_INFORMADO)
    df["year"] = df["order_date"].dt.year
    df["month"] = df["order_date"].dt.month
    df["year_month"] = df["order_date"].dt.to_period("M").astype(str)
    df["weekday"] = df["order_date"].dt.day_name()
    # só pedidos entregues contam como receita realizada
    df["is_valid_sale"] = df["status"].eq("Entregue")

    df = df.sort_values(["order_date", "order_id"]).reset_index(drop=True)

    report["linhas_finais"] = len(df)
    report["nulos_depois"] = int(df.isna().sum().sum())
    return df, report


def print_report(report: dict):
    print("\n" + "=" * 50)
    print("RELATÓRIO DE LIMPEZA")
    print("=" * 50)
    print(f"Linhas originais:               {report['linhas_originais']:>7,}")
    print(f"Duplicatas removidas:           {report['duplicatas_removidas']:>7,}")
    print(f"Datas inválidas descartadas:    {report['datas_invalidas']:>7,}")
    print(f"Preços convertidos de texto:    {report['precos_convertidos_de_texto']:>7,}")
    print(f"Categorias padronizadas:        {report['categorias_padronizadas']:>7,}")
    print(f"Estados padronizados:           {report['estados_padronizados']:>7,}")
    print(f"Quantidades outlier corrigidas: {report['quantidades_outlier_corrigidas']:>7,}")
    print(f"Linhas finais:                  {report['linhas_finais']:>7,}")
    print("\nNulos encontrados antes da limpeza:")
    for col, n in report["nulos_antes"].items():
        print(f"  - {col}: {n:,}")
    print(f"\nNulos restantes na base final: {report['nulos_depois']}")
    print("=" * 50 + "\n")


def main():
    if not RAW_PATH.exists():
        raise SystemExit(
            f"Arquivo não encontrado: {RAW_PATH}\n"
            "Rode primeiro: python src/generate_data.py"
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(RAW_PATH)
    clean_df, report = clean(raw)
    print_report(report)

    clean_df.to_csv(OUT_DIR / "vendas_clean.csv", index=False, encoding="utf-8")
    with open(OUT_DIR / "cleaning_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Base limpa salva em: {OUT_DIR / 'vendas_clean.csv'}")
    print(f"Relatório salvo em:  {OUT_DIR / 'cleaning_report.json'}")


if __name__ == "__main__":
    main()
