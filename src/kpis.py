"""
kpis.py
Lê a base limpa (data/processed/vendas_clean.csv), calcula os indicadores
principais e salva tudo em data/processed/kpis.json (o dashboard web vai
consumir esse arquivo).

Regra de negócio: receita, lucro e ticket médio consideram apenas pedidos
ENTREGUES (is_valid_sale). Cancelados e devolvidos entram só nas taxas.

Uso (na raiz do projeto):
    python src/kpis.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLEAN_PATH = ROOT / "data" / "processed" / "vendas_clean.csv"
OUT_PATH = ROOT / "data" / "processed" / "kpis.json"


def load() -> pd.DataFrame:
    df = pd.read_csv(CLEAN_PATH, parse_dates=["order_date"])
    df["is_valid_sale"] = df["is_valid_sale"].astype(bool)
    return df


def pct_change(current: float, previous: float):
    if previous in (0, None) or pd.isna(previous):
        return None
    return round((current - previous) / previous * 100, 1)


def summary_block(sales: pd.DataFrame, all_rows: pd.DataFrame) -> dict:
    """Indicadores-resumo de um conjunto de vendas válidas."""
    revenue = sales["net_revenue"].sum()
    profit = sales["profit"].sum()
    orders = sales["order_id"].nunique()
    return {
        "receita_liquida": round(revenue, 2),
        "lucro": round(profit, 2),
        "margem_pct": round(profit / revenue * 100, 1) if revenue else 0,
        "pedidos": int(orders),
        "ticket_medio": round(revenue / orders, 2) if orders else 0,
        "itens_vendidos": int(sales["quantity"].sum()),
        "clientes_ativos": int(sales["customer_id"].nunique()),
        "desconto_medio_pct": round(sales["discount_pct"].mean(), 1) if len(sales) else 0,
    }


def status_rates(df: pd.DataFrame) -> dict:
    """Taxas por pedido (cada pedido tem um único status)."""
    orders = df.drop_duplicates("order_id")
    total = len(orders)
    counts = orders["status"].value_counts()
    return {
        "total_pedidos": int(total),
        "taxa_cancelamento_pct": round(counts.get("Cancelado", 0) / total * 100, 1),
        "taxa_devolucao_pct": round(counts.get("Devolvido", 0) / total * 100, 1),
        "taxa_entrega_pct": round(counts.get("Entregue", 0) / total * 100, 1),
    }


def group_table(sales: pd.DataFrame, by: str) -> pd.DataFrame:
    """Tabela padrão: receita, lucro, margem e pedidos por dimensão."""
    g = sales.groupby(by).agg(
        receita=("net_revenue", "sum"),
        lucro=("profit", "sum"),
        pedidos=("order_id", "nunique"),
        itens=("quantity", "sum"),
    )
    g["margem_pct"] = (g["lucro"] / g["receita"] * 100).round(1)
    g["ticket_medio"] = (g["receita"] / g["pedidos"]).round(2)
    g["participacao_pct"] = (g["receita"] / g["receita"].sum() * 100).round(1)
    g[["receita", "lucro"]] = g[["receita", "lucro"]].round(2)
    return g.sort_values("receita", ascending=False).reset_index()


def compute_kpis(df: pd.DataFrame) -> dict:
    sales = df[df["is_valid_sale"]]
    k = {}

    # --- período e visão geral -------------------------------------------
    k["periodo"] = {
        "inicio": df["order_date"].min().strftime("%Y-%m-%d"),
        "fim": df["order_date"].max().strftime("%Y-%m-%d"),
    }
    k["geral"] = summary_block(sales, df)
    k["status"] = status_rates(df)

    # --- comparação entre anos (YoY) -------------------------------------
    years = sorted(sales["year"].unique())
    k["por_ano"] = {}
    for y in years:
        k["por_ano"][str(y)] = summary_block(sales[sales["year"] == y], df)
    if len(years) >= 2:
        cur, prev = k["por_ano"][str(years[-1])], k["por_ano"][str(years[-2])]
        k["crescimento_anual"] = {
            "ano_atual": int(years[-1]),
            "ano_anterior": int(years[-2]),
            "receita_pct": pct_change(cur["receita_liquida"], prev["receita_liquida"]),
            "lucro_pct": pct_change(cur["lucro"], prev["lucro"]),
            "pedidos_pct": pct_change(cur["pedidos"], prev["pedidos"]),
            "ticket_medio_pct": pct_change(cur["ticket_medio"], prev["ticket_medio"]),
        }

    # --- série mensal -----------------------------------------------------
    monthly = group_table(sales, "year_month").sort_values("year_month")
    monthly["var_mensal_pct"] = monthly["receita"].pct_change().mul(100).round(1)
    k["mensal"] = monthly.replace({np.nan: None}).to_dict("records")

    # --- cortes por dimensão ---------------------------------------------
    k["por_categoria"] = group_table(sales, "category").to_dict("records")
    k["por_regiao"] = group_table(sales, "region").to_dict("records")
    k["por_estado"] = group_table(sales, "state").to_dict("records")
    k["por_canal"] = group_table(sales, "channel").to_dict("records")
    k["por_pagamento"] = group_table(sales, "payment_method").to_dict("records")

    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday",
                     "Friday", "Saturday", "Sunday"]
    wd = group_table(sales, "weekday").set_index("weekday").reindex(weekday_order)
    k["por_dia_semana"] = wd.reset_index().to_dict("records")

    # --- rankings ----------------------------------------------------------
    products = group_table(sales, ["product_name", "category"])
    k["top_produtos_receita"] = products.head(10).to_dict("records")
    k["top_produtos_lucro"] = (
        products.sort_values("lucro", ascending=False).head(10).to_dict("records")
    )
    k["top_produtos_volume"] = (
        products.sort_values("itens", ascending=False).head(10).to_dict("records")
    )

    cust = (
        sales.groupby(["customer_id", "customer_name"])
        .agg(receita=("net_revenue", "sum"), pedidos=("order_id", "nunique"))
        .sort_values("receita", ascending=False)
        .head(10)
        .round(2)
        .reset_index()
    )
    k["top_clientes"] = cust.to_dict("records")

    # --- recorrência de clientes ------------------------------------------
    orders_per_customer = sales.groupby("customer_id")["order_id"].nunique()
    k["recorrencia"] = {
        "clientes_compra_unica": int((orders_per_customer == 1).sum()),
        "clientes_recorrentes": int((orders_per_customer > 1).sum()),
        "taxa_recompra_pct": round((orders_per_customer > 1).mean() * 100, 1),
    }

    # --- perdas: cancelamentos e devoluções por categoria ------------------
    orders_cat = df.drop_duplicates(["order_id", "category"])
    loss = (
        orders_cat.assign(problema=orders_cat["status"].isin(["Cancelado", "Devolvido"]))
        .groupby("category")["problema"]
        .mean()
        .mul(100)
        .round(1)
        .sort_values(ascending=False)
    )
    k["perda_por_categoria"] = [
        {"category": c, "taxa_problema_pct": v} for c, v in loss.items()
    ]
    return k


def print_summary(k: dict):
    g, s = k["geral"], k["status"]
    print("\n" + "=" * 50)
    print("INDICADORES PRINCIPAIS")
    print("=" * 50)
    print(f"Período:          {k['periodo']['inicio']} a {k['periodo']['fim']}")
    print(f"Receita líquida:  R$ {g['receita_liquida']:,.2f}")
    print(f"Lucro:            R$ {g['lucro']:,.2f}  (margem {g['margem_pct']}%)")
    print(f"Pedidos:          {g['pedidos']:,}")
    print(f"Ticket médio:     R$ {g['ticket_medio']:,.2f}")
    print(f"Clientes ativos:  {g['clientes_ativos']:,}")
    print(f"Cancelamento:     {s['taxa_cancelamento_pct']}%   Devolução: {s['taxa_devolucao_pct']}%")
    if "crescimento_anual" in k:
        c = k["crescimento_anual"]
        print(f"Crescimento {c['ano_anterior']} -> {c['ano_atual']}: "
              f"receita {c['receita_pct']}%, pedidos {c['pedidos_pct']}%")
    top = k["top_produtos_receita"][0]
    print(f"Produto nº 1:     {top['product_name']} (R$ {top['receita']:,.2f})")
    print(f"Categoria nº 1:   {k['por_categoria'][0]['category']}")
    print(f"Região nº 1:      {k['por_regiao'][0]['region']}")
    print("=" * 50 + "\n")


def main():
    if not CLEAN_PATH.exists():
        raise SystemExit(
            f"Arquivo não encontrado: {CLEAN_PATH}\n"
            "Rode primeiro: python src/cleaning.py"
        )
    df = load()
    kpis = compute_kpis(df)
    print_summary(kpis)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(kpis, f, ensure_ascii=False, indent=2)
    print(f"KPIs salvos em: {OUT_PATH}")

    # Cópia em .js para o dashboard abrir direto no navegador (sem servidor)
    js_path = ROOT / "web" / "kpis_data.js"
    js_path.parent.mkdir(exist_ok=True)
    js_path.write_text(
        "window.KPIS = " + json.dumps(kpis, ensure_ascii=False) + ";", encoding="utf-8"
    )
    print(f"Dados do dashboard salvos em: {js_path}")


if __name__ == "__main__":
    main()
