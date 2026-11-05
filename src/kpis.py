"""
kpis.py
Calcula os indicadores a partir da base limpa. Só calcula o que os dados do
cliente permitem: sem coluna de custo, não há lucro/margem; sem coluna de
status, não há taxas de cancelamento, e assim por diante.

Regra de negócio: receita, lucro e ticket médio consideram apenas as vendas
válidas (is_valid_sale). Cancelados e devolvidos entram só nas taxas.

Este arquivo não é executado direto. Use:  python src/run.py
"""

import numpy as np
import pandas as pd


def pct_change(current, previous):
    if previous in (0, None) or pd.isna(previous):
        return None
    return round((current - previous) / previous * 100, 1)


def summary_block(sales: pd.DataFrame) -> dict:
    revenue = sales["net_revenue"].sum()
    orders = sales["order_id"].nunique()
    out = {
        "receita_liquida": round(revenue, 2),
        "pedidos": int(orders),
        "ticket_medio": round(revenue / orders, 2) if orders else 0,
        "itens_vendidos": int(sales["quantity"].sum()),
        "desconto_medio_pct": round(sales["discount_pct"].mean(), 1) if len(sales) else 0,
        "lucro": None, "margem_pct": None, "clientes_ativos": None,
    }
    if "profit" in sales:
        profit = sales["profit"].sum()
        out["lucro"] = round(profit, 2)
        out["margem_pct"] = round(profit / revenue * 100, 1) if revenue else 0
    if "customer_id" in sales:
        out["clientes_ativos"] = int(sales["customer_id"].nunique())
    return out


def status_rates(df: pd.DataFrame, cfg: dict) -> dict:
    """Taxas por pedido (cada pedido tem um único status)."""
    low = lambda key, default: [s.lower() for s in cfg.get(key, default)]
    validos = low("status_venda_valida", ["Entregue"])
    cancel = low("status_cancelado", ["Cancelado"])
    devol = low("status_devolvido", ["Devolvido"])
    st = df.drop_duplicates("order_id")["status"].str.lower()
    total = len(st)
    return {
        "total_pedidos": int(total),
        "taxa_cancelamento_pct": round(st.isin(cancel).mean() * 100, 1),
        "taxa_devolucao_pct": round(st.isin(devol).mean() * 100, 1),
        "taxa_entrega_pct": round(st.isin(validos).mean() * 100, 1),
    }


def group_table(sales: pd.DataFrame, by) -> pd.DataFrame:
    """Tabela padrão por dimensão: receita, pedidos, ticket, participação (e lucro/margem, se houver)."""
    aggs = dict(receita=("net_revenue", "sum"), pedidos=("order_id", "nunique"), itens=("quantity", "sum"))
    has_profit = "profit" in sales
    if has_profit:
        aggs["lucro"] = ("profit", "sum")
    g = sales.groupby(by).agg(**aggs)
    g["ticket_medio"] = (g["receita"] / g["pedidos"]).round(2)
    g["participacao_pct"] = (g["receita"] / g["receita"].sum() * 100).round(1)
    if has_profit:
        g["margem_pct"] = (g["lucro"] / g["receita"] * 100).round(1)
        g["lucro"] = g["lucro"].round(2)
    g["receita"] = g["receita"].round(2)
    return g.sort_values("receita", ascending=False).reset_index()


def compute_kpis(df: pd.DataFrame, cfg: dict) -> dict:
    sales = df[df["is_valid_sale"]]
    has = lambda c: c in df.columns
    k = {"cliente": cfg.get("cliente", "")}

    k["periodo"] = {
        "inicio": df["order_date"].min().strftime("%Y-%m-%d"),
        "fim": df["order_date"].max().strftime("%Y-%m-%d"),
    }
    k["disponivel"] = {  # o que existe nos dados deste cliente
        "lucro": has("profit"), "status": has("status"), "clientes": has("customer_id"),
        "categoria": has("category"), "regiao": has("region"), "canal": has("channel"),
        "produto": has("product_name"),
    }
    k["geral"] = summary_block(sales)
    k["status"] = status_rates(df, cfg) if has("status") else None

    # --- comparação entre anos -------------------------------------------
    years = sorted(sales["year"].unique())
    k["por_ano"] = {str(y): summary_block(sales[sales["year"] == y]) for y in years}
    if len(years) >= 2:
        cur, prev = k["por_ano"][str(years[-1])], k["por_ano"][str(years[-2])]
        k["crescimento_anual"] = {
            "ano_atual": int(years[-1]), "ano_anterior": int(years[-2]),
            "receita_pct": pct_change(cur["receita_liquida"], prev["receita_liquida"]),
            "lucro_pct": pct_change(cur["lucro"], prev["lucro"]) if has("profit") else None,
            "pedidos_pct": pct_change(cur["pedidos"], prev["pedidos"]),
            "ticket_medio_pct": pct_change(cur["ticket_medio"], prev["ticket_medio"]),
        }

    # --- série mensal e dia da semana -------------------------------------
    monthly = group_table(sales, "year_month").sort_values("year_month")
    monthly["var_mensal_pct"] = monthly["receita"].pct_change().mul(100).round(1)
    k["mensal"] = monthly.replace({np.nan: None}).to_dict("records")

    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    wd = group_table(sales, "weekday").set_index("weekday").reindex(order)
    k["por_dia_semana"] = wd.reset_index().replace({np.nan: None}).to_dict("records")

    # --- cortes opcionais (só se a coluna existir) ------------------------
    for key, col in [("por_categoria", "category"), ("por_regiao", "region"), ("por_estado", "state"),
                     ("por_canal", "channel"), ("por_pagamento", "payment_method")]:
        k[key] = group_table(sales, col).to_dict("records") if has(col) else None

    # --- rankings ----------------------------------------------------------
    if has("product_name"):
        by = ["product_name"] + (["category"] if has("category") else [])
        products = group_table(sales, by)
        k["top_produtos_receita"] = products.head(10).to_dict("records")
        k["top_produtos_volume"] = products.sort_values("itens", ascending=False).head(10).to_dict("records")
        k["top_produtos_lucro"] = (
            products.sort_values("lucro", ascending=False).head(10).to_dict("records")
            if has("profit") else None
        )
    else:
        k["top_produtos_receita"] = k["top_produtos_volume"] = k["top_produtos_lucro"] = None

    if has("customer_id"):
        keys = ["customer_id"] + (["customer_name"] if has("customer_name") else [])
        k["top_clientes"] = (
            sales.groupby(keys)
            .agg(receita=("net_revenue", "sum"), pedidos=("order_id", "nunique"))
            .sort_values("receita", ascending=False).head(10).round(2).reset_index()
            .to_dict("records")
        )
        opc = sales.groupby("customer_id")["order_id"].nunique()
        k["recorrencia"] = {
            "clientes_compra_unica": int((opc == 1).sum()),
            "clientes_recorrentes": int((opc > 1).sum()),
            "taxa_recompra_pct": round((opc > 1).mean() * 100, 1),
        }
    else:
        k["top_clientes"] = k["recorrencia"] = None

    # --- perdas por categoria ---------------------------------------------
    k["perda_por_categoria"] = None
    if has("status") and has("category"):
        perdas = [s.lower() for s in cfg.get("status_cancelado", ["Cancelado"])
                  + cfg.get("status_devolvido", ["Devolvido"])]
        oc = df.drop_duplicates(["order_id", "category"])
        loss = (oc.assign(p=oc["status"].str.lower().isin(perdas))
                .groupby("category")["p"].mean().mul(100).round(1).sort_values(ascending=False))
        k["perda_por_categoria"] = [{"category": c, "taxa_problema_pct": v} for c, v in loss.items()]
    return k


def print_summary(k: dict):
    g, s = k["geral"], k["status"]
    print("\n" + "=" * 52)
    print(f"INDICADORES PRINCIPAIS  {('- ' + k['cliente']) if k['cliente'] else ''}")
    print("=" * 52)
    print(f"Período:          {k['periodo']['inicio']} a {k['periodo']['fim']}")
    print(f"Receita líquida:  R$ {g['receita_liquida']:,.2f}")
    if g["lucro"] is not None:
        print(f"Lucro:            R$ {g['lucro']:,.2f}  (margem {g['margem_pct']}%)")
    else:
        print("Lucro:            (sem coluna de custo na planilha, indicador pulado)")
    print(f"Pedidos:          {g['pedidos']:,}")
    print(f"Ticket médio:     R$ {g['ticket_medio']:,.2f}")
    if g["clientes_ativos"] is not None:
        print(f"Clientes ativos:  {g['clientes_ativos']:,}")
    if s:
        print(f"Cancelamento:     {s['taxa_cancelamento_pct']}%   Devolução: {s['taxa_devolucao_pct']}%")
    if "crescimento_anual" in k:
        c = k["crescimento_anual"]
        print(f"Crescimento {c['ano_anterior']} -> {c['ano_atual']}: receita {c['receita_pct']}%, pedidos {c['pedidos_pct']}%")
    if k["top_produtos_receita"]:
        top = k["top_produtos_receita"][0]
        print(f"Produto nº 1:     {top['product_name']} (R$ {top['receita']:,.2f})")
    print("=" * 52 + "\n")