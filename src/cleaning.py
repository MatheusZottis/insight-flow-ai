"""
cleaning.py
Limpeza genérica: recebe a planilha bruta de um cliente + a configuração dele
(mapeamento de colunas) e devolve a base limpa com colunas padronizadas.

Este arquivo não é executado direto. Use:  python src/run.py
"""

import re
import unicodedata

import numpy as np
import pandas as pd

REGIONS = {
    "SP": "Sudeste", "RJ": "Sudeste", "MG": "Sudeste", "ES": "Sudeste",
    "PR": "Sul", "SC": "Sul", "RS": "Sul",
    "BA": "Nordeste", "PE": "Nordeste", "CE": "Nordeste", "MA": "Nordeste",
    "PB": "Nordeste", "RN": "Nordeste", "AL": "Nordeste", "SE": "Nordeste", "PI": "Nordeste",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MT": "Centro-Oeste", "MS": "Centro-Oeste",
    "PA": "Norte", "AM": "Norte", "AC": "Norte", "AP": "Norte", "RO": "Norte",
    "RR": "Norte", "TO": "Norte",
}
STATE_NAMES = {"são paulo": "SP", "sao paulo": "SP", "rio de janeiro": "RJ", "minas gerais": "MG"}
NAO_INFORMADO = "Não informado"

# Colunas que o cliente PRECISA ter (nome interno -> descrição)
REQUIRED = {
    "order_date": "data do pedido",
    "order_id": "número/identificador do pedido",
    "quantity": "quantidade",
    "unit_price": "preço unitário",
}
# Colunas de texto cujos nulos viram "Não informado"
TEXT_FILL = ["email", "city", "state", "channel", "payment_method",
             "category", "product_name", "customer_name"]


# ----------------------------------------------------------------------
# Funções auxiliares
# ----------------------------------------------------------------------
def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def parse_date(value, dayfirst=True):
    """Aceita 2024-05-10, 10/05/2024 e 10-05-2024 (ou mês primeiro, se configurado)."""
    if pd.isna(value):
        return pd.NaT
    s = str(value).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return pd.to_datetime(s[:10], format="%Y-%m-%d", errors="coerce")
    sep = "/" if "/" in s else "-"
    fmt = f"%d{sep}%m{sep}%Y" if dayfirst else f"%m{sep}%d{sep}%Y"
    return pd.to_datetime(s[:10], format=fmt, errors="coerce")


def parse_price(value):
    """Converte 1299.9, 'R$ 1.299,90' e '70,05' para float."""
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
    """Preenche nulos usando outras linhas do mesmo grupo (mesmo cliente, mesmo pedido)."""
    def first_valid(s):
        valid = s.dropna()
        return valid.iloc[0] if len(valid) else np.nan

    return df[target_col].fillna(df.groupby(group_col)[target_col].transform(first_valid))


def normalize_categories(series):
    """Agrupa variações de maiúsculas, espaços e acentos na forma mais frequente."""
    s = series.replace(r"^\s*$", np.nan, regex=True)
    mask = s.notna()
    s[mask] = s[mask].astype(str).str.strip()
    key = s[mask].apply(lambda x: strip_accents(x).lower())
    canonical = s[mask].groupby(key).agg(lambda x: x.value_counts().index[0])
    changed = int((s[mask] != key.map(canonical)).sum())
    s[mask] = key.map(canonical)
    return s, changed


def norm_state(s):
    if pd.isna(s):
        return np.nan
    s = str(s).strip()
    return STATE_NAMES.get(s.lower(), s.upper())


def apply_mapping(df, cfg):
    """Renomeia as colunas do cliente para os nomes internos e valida as obrigatórias."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    mapa = cfg.get("colunas", {})

    faltando = [k for k in REQUIRED if k not in mapa or mapa[k] not in df.columns]
    if faltando:
        linhas = [f"  - {k} ({REQUIRED[k]}): configurado como '{mapa.get(k, '(não configurado)')}'"
                  for k in faltando]
        raise ValueError(
            "Colunas obrigatórias não encontradas na planilha:\n" + "\n".join(linhas)
            + "\n\nColunas que existem na planilha:\n  " + ", ".join(df.columns)
            + "\n\nCorrija o arquivo de configuração (seção 'colunas')."
        )

    rename = {v: k for k, v in mapa.items() if v in df.columns}
    ausentes = [k for k, v in mapa.items() if v not in df.columns]
    return df[list(rename)].rename(columns=rename), ausentes


# ----------------------------------------------------------------------
# Pipeline de limpeza
# ----------------------------------------------------------------------
def clean(df: pd.DataFrame, cfg: dict):
    report = {"linhas_originais": len(df)}
    df, ausentes = apply_mapping(df, cfg)
    report["colunas_opcionais_ausentes"] = ausentes

    # 1. Duplicatas exatas
    n = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    report["duplicatas_removidas"] = n - len(df)

    # 2. Tipos essenciais: data, preço, quantidade
    dayfirst = cfg.get("formato_data", "dia_primeiro") == "dia_primeiro"
    df["order_date"] = df["order_date"].apply(lambda v: parse_date(v, dayfirst))
    report["datas_invalidas"] = int(df["order_date"].isna().sum())

    report["precos_convertidos_de_texto"] = int(
        df["unit_price"].astype(str).str.contains(r"R\$", regex=True).sum()
    )
    df["unit_price"] = df["unit_price"].apply(parse_price)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    for col in ["unit_cost", "shipping_fee"]:
        if col in df:
            df[col] = df[col].apply(parse_price)
    if "discount_pct" in df:
        df["discount_pct"] = pd.to_numeric(df["discount_pct"], errors="coerce")

    invalid = (df[["order_date", "unit_price", "quantity", "order_id"]].isna().any(axis=1))
    report["linhas_descartadas_dados_essenciais"] = int(invalid.sum())
    df = df[~invalid].copy()

    # 3. Categorias e produtos
    report["categorias_padronizadas"] = 0
    if "category" in df:
        df["category"], report["categorias_padronizadas"] = normalize_categories(df["category"])
    if "product_name" in df:
        df["product_name"] = df["product_name"].where(df["product_name"].isna(),
                                                      df["product_name"].astype(str).str.strip())

    # 4. Estados
    report["estados_padronizados"] = 0
    if "state" in df:
        antes = df["state"].copy()
        df["state"] = df["state"].apply(norm_state)
        report["estados_padronizados"] = int(((antes != df["state"]) & antes.notna()).sum())

    # 5. Nulos
    report["nulos_antes"] = {k: int(v) for k, v in df.isna().sum().items() if v > 0}

    if "customer_id" in df:   # recupera dados do cliente em outras compras dele
        for col in ["email", "city", "state", "customer_name"]:
            if col in df:
                df[col] = fill_from_group(df, "customer_id", col)
    for col in ["channel", "payment_method", "discount_pct"]:   # dados do pedido
        if col in df:
            df[col] = fill_from_group(df, "order_id", col)
    for col in TEXT_FILL:
        if col in df:
            df[col] = df[col].fillna(NAO_INFORMADO)
    df["discount_pct"] = df["discount_pct"].fillna(0).astype(float) if "discount_pct" in df else 0.0

    # 6. Outliers de quantidade
    qmax = cfg.get("quantidade_maxima", 20)
    outliers = (df["quantity"] > qmax) if qmax else pd.Series(False, index=df.index)
    report["quantidades_outlier_corrigidas"] = int(outliers.sum())
    df.loc[outliers, "quantity"] = 1
    df["quantity"] = df["quantity"].astype(int)

    # 7. Colunas derivadas
    df["gross_revenue"] = (df["quantity"] * df["unit_price"]).round(2)
    df["discount_value"] = (df["gross_revenue"] * df["discount_pct"] / 100).round(2)
    df["net_revenue"] = (df["gross_revenue"] - df["discount_value"]).round(2)
    if "unit_cost" in df:
        df["total_cost"] = (df["quantity"] * df["unit_cost"]).round(2)
        df["profit"] = (df["net_revenue"] - df["total_cost"]).round(2)
    if "state" in df:
        region = df["state"].map(REGIONS)
        if region.notna().mean() >= 0.5:   # só cria região se os estados forem brasileiros
            df["region"] = region.fillna(NAO_INFORMADO)
    df["year"] = df["order_date"].dt.year
    df["month"] = df["order_date"].dt.month
    df["year_month"] = df["order_date"].dt.to_period("M").astype(str)
    df["weekday"] = df["order_date"].dt.day_name()

    if "status" in df:
        df["status"] = df["status"].astype(str).str.strip()
        validos = [s.lower() for s in cfg.get("status_venda_valida", ["Entregue"])]
        df["is_valid_sale"] = df["status"].str.lower().isin(validos)
    else:
        df["is_valid_sale"] = True

    df = df.sort_values(["order_date", "order_id"]).reset_index(drop=True)
    report["linhas_finais"] = len(df)
    report["nulos_depois"] = int(df.isna().sum().sum())
    return df, report


def print_report(report: dict):
    r = report
    print("\n" + "=" * 52)
    print("RELATÓRIO DE LIMPEZA")
    print("=" * 52)
    print(f"Linhas originais:                {r['linhas_originais']:>7,}")
    print(f"Duplicatas removidas:            {r['duplicatas_removidas']:>7,}")
    print(f"Datas inválidas:                 {r['datas_invalidas']:>7,}")
    print(f"Linhas descartadas (essenciais): {r['linhas_descartadas_dados_essenciais']:>7,}")
    print(f"Preços convertidos de texto:     {r['precos_convertidos_de_texto']:>7,}")
    print(f"Categorias padronizadas:         {r['categorias_padronizadas']:>7,}")
    print(f"Estados padronizados:            {r['estados_padronizados']:>7,}")
    print(f"Quantidades outlier corrigidas:  {r['quantidades_outlier_corrigidas']:>7,}")
    print(f"Linhas finais:                   {r['linhas_finais']:>7,}")
    if r["nulos_antes"]:
        print("\nNulos encontrados antes da limpeza:")
        for col, n in r["nulos_antes"].items():
            print(f"  - {col}: {n:,}")
    if r["colunas_opcionais_ausentes"]:
        print("\nColunas opcionais não encontradas (indicadores que dependem delas serão pulados):")
        print("  " + ", ".join(r["colunas_opcionais_ausentes"]))
    print(f"\nNulos restantes na base final: {r['nulos_depois']}")
    print("=" * 52 + "\n")