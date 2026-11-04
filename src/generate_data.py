"""
generate_data.py
Gera uma base fictícia, mas realista, de vendas de e-commerce brasileiro.
A base sai "suja" de propósito (datas mistas, nulos, duplicatas, categorias
escritas de várias formas, preços como texto) para treinar/mostrar a limpeza.

Uso (na raiz do projeto):
    python src/generate_data.py

Saída:
    data/raw/vendas_raw.csv
    data/raw/vendas_raw.xlsx
"""

from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

SEED = 42
N_ORDERS = 9000
START, END = "2024-01-01", "2025-12-31"

rng = np.random.default_rng(SEED)
fake = Faker("pt_BR")
Faker.seed(SEED)

# ----------------------------------------------------------------------
# 1. Catálogo de produtos: (categoria, nome, preço, custo como % do preço)
# ----------------------------------------------------------------------
CATALOG = [
    ("Eletrônicos", "Smartphone Galaxy A15", 1299.90, 0.72),
    ("Eletrônicos", "Fone Bluetooth ProSound", 199.90, 0.45),
    ("Eletrônicos", "Smartwatch Fit Band 5", 349.90, 0.55),
    ("Eletrônicos", "Caixa de Som Portátil Boom", 279.90, 0.50),
    ("Eletrônicos", "Carregador Turbo 65W", 89.90, 0.35),
    ("Eletrônicos", "Notebook Ultra 14", 3899.00, 0.78),
    ("Eletrônicos", "Tablet Tab Plus 10", 1499.00, 0.70),
    ("Eletrônicos", "Mouse Sem Fio Slim", 69.90, 0.38),
    ("Casa e Decoração", "Luminária de Mesa LED", 119.90, 0.42),
    ("Casa e Decoração", "Jogo de Cama Queen 400 fios", 229.90, 0.48),
    ("Casa e Decoração", "Kit 6 Taças de Vidro", 79.90, 0.40),
    ("Casa e Decoração", "Tapete Sala 2x1,5m", 259.90, 0.50),
    ("Casa e Decoração", "Organizador Multiuso", 49.90, 0.30),
    ("Casa e Decoração", "Espelho Decorativo Redondo", 189.90, 0.45),
    ("Moda", "Camiseta Básica Algodão", 59.90, 0.30),
    ("Moda", "Calça Jeans Slim", 159.90, 0.38),
    ("Moda", "Tênis Casual Urban", 279.90, 0.50),
    ("Moda", "Jaqueta Corta-Vento", 219.90, 0.45),
    ("Moda", "Mochila Executiva", 169.90, 0.40),
    ("Moda", "Vestido Midi Floral", 139.90, 0.35),
    ("Beleza e Saúde", "Perfume Floral 100ml", 249.90, 0.40),
    ("Beleza e Saúde", "Kit Skincare Facial", 189.90, 0.38),
    ("Beleza e Saúde", "Secador de Cabelo 2000W", 149.90, 0.50),
    ("Beleza e Saúde", "Protetor Solar FPS 60", 54.90, 0.35),
    ("Beleza e Saúde", "Whey Protein 900g", 129.90, 0.55),
    ("Esporte e Lazer", "Bicicleta Aro 29", 1599.00, 0.65),
    ("Esporte e Lazer", "Kit Halteres 10kg", 189.90, 0.50),
    ("Esporte e Lazer", "Tapete de Yoga", 79.90, 0.35),
    ("Esporte e Lazer", "Garrafa Térmica 1L", 99.90, 0.38),
    ("Esporte e Lazer", "Barraca Camping 4 Pessoas", 459.90, 0.55),
    ("Livros e Papelaria", "Livro Best-Seller Ficção", 49.90, 0.55),
    ("Livros e Papelaria", "Caderno Inteligente A5", 69.90, 0.40),
    ("Livros e Papelaria", "Kit Canetas Gel 12un", 29.90, 0.30),
    ("Livros e Papelaria", "Agenda 2025 Premium", 59.90, 0.38),
    ("Brinquedos", "Blocos de Montar 500 peças", 149.90, 0.45),
    ("Brinquedos", "Boneca Interativa", 189.90, 0.48),
    ("Brinquedos", "Carrinho Controle Remoto", 159.90, 0.50),
    ("Brinquedos", "Jogo de Tabuleiro Estratégia", 129.90, 0.45),
    ("Pet Shop", "Ração Premium Cães 10kg", 179.90, 0.60),
    ("Pet Shop", "Arranhador para Gatos", 119.90, 0.40),
    ("Pet Shop", "Cama Pet Confort M", 99.90, 0.38),
]
# Ajuste de margem: custo mais alto = margem mais realista para e-commerce
CATALOG = [(c, n, p, round(min(r + 0.15, 0.88), 2)) for c, n, p, r in CATALOG]

# Peso de popularidade: itens baratos vendem mais
prices = np.array([p[2] for p in CATALOG])
pop = 1 / np.sqrt(prices)
pop = pop / pop.sum()

# ----------------------------------------------------------------------
# 2. Geografia, canais, pagamentos
# ----------------------------------------------------------------------
STATES = {
    "SP": (0.32, ["São Paulo", "Campinas", "Santos", "Ribeirão Preto", "Sorocaba"]),
    "RJ": (0.12, ["Rio de Janeiro", "Niterói", "Petrópolis"]),
    "MG": (0.11, ["Belo Horizonte", "Uberlândia", "Juiz de Fora"]),
    "RS": (0.06, ["Porto Alegre", "Caxias do Sul"]),
    "PR": (0.06, ["Curitiba", "Londrina", "Maringá"]),
    "SC": (0.05, ["Florianópolis", "Joinville", "Blumenau"]),
    "BA": (0.06, ["Salvador", "Feira de Santana"]),
    "PE": (0.04, ["Recife", "Olinda"]),
    "CE": (0.04, ["Fortaleza", "Juazeiro do Norte"]),
    "DF": (0.04, ["Brasília"]),
    "GO": (0.04, ["Goiânia", "Anápolis"]),
    "PA": (0.02, ["Belém"]),
    "AM": (0.02, ["Manaus"]),
    "ES": (0.02, ["Vitória", "Vila Velha"]),
}
state_codes = list(STATES)
state_w = np.array([STATES[s][0] for s in state_codes])
state_w = state_w / state_w.sum()

# Frete médio por estado (mais longe do Sudeste = mais caro)
SHIPPING_BASE = {
    "SP": 14, "RJ": 18, "MG": 19, "ES": 20, "PR": 20, "SC": 22, "RS": 25,
    "DF": 28, "GO": 28, "BA": 32, "PE": 35, "CE": 38, "PA": 45, "AM": 52,
}

CHANNELS = ["Site Próprio", "App Mobile", "Marketplace", "Redes Sociais"]
CHANNEL_W = [0.38, 0.27, 0.25, 0.10]

PAYMENTS = ["Cartão de Crédito", "Pix", "Boleto", "Cartão de Débito"]
PAYMENT_W = [0.48, 0.34, 0.11, 0.07]

STATUS = ["Entregue", "Cancelado", "Devolvido"]
STATUS_W = [0.87, 0.07, 0.06]


# ----------------------------------------------------------------------
# 3. Clientes
# ----------------------------------------------------------------------
def build_customers(n=3500):
    states = rng.choice(state_codes, size=n, p=state_w)
    rows = []
    for i, st in enumerate(states, start=1):
        name = fake.name()
        rows.append(
            {
                "customer_id": f"C{i:05d}",
                "customer_name": name,
                "email": fake.email(),
                "state": st,
                "city": rng.choice(STATES[st][1]),
            }
        )
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# 4. Datas com sazonalidade + crescimento
# ----------------------------------------------------------------------
def sample_dates(n):
    days = pd.date_range(START, END, freq="D")
    month_w = {1: .85, 2: .80, 3: .90, 4: .90, 5: 1.20, 6: 1.00,
               7: .95, 8: 1.00, 9: 1.00, 10: 1.05, 11: 1.70, 12: 1.45}
    w = np.array([month_w[d.month] for d in days], dtype=float)

    # tendência de crescimento: +35% ao longo do período
    trend = np.linspace(1.0, 1.35, len(days))
    w *= trend

    # pico na Black Friday (última sexta de novembro) e Dia das Mães
    for y in (2024, 2025):
        nov = pd.date_range(f"{y}-11-01", f"{y}-11-30")
        bf = [d for d in nov if d.weekday() == 4][-1]
        for k, d in enumerate(days):
            if abs((d - bf).days) <= 1:
                w[k] *= 2.6
        # fins de semana um pouco mais fracos, terça a quinta normais
    weekday_w = {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.1, 5: .9, 6: .85}
    w *= np.array([weekday_w[d.weekday()] for d in days])

    w = w / w.sum()
    idx = rng.choice(len(days), size=n, p=w)
    return days[idx]


# ----------------------------------------------------------------------
# 5. Monta as linhas (um pedido pode ter 1 a 3 itens)
# ----------------------------------------------------------------------
def build_sales():
    customers = build_customers()
    order_dates = sample_dates(N_ORDERS)
    cust_idx = rng.choice(
        len(customers), size=N_ORDERS,
        p=_customer_weights(len(customers)),
    )

    rows = []
    for o in range(N_ORDERS):
        order_id = f"PED{100000 + o}"
        date = order_dates[o]
        cust = customers.iloc[cust_idx[o]]
        channel = rng.choice(CHANNELS, p=CHANNEL_W)
        payment = rng.choice(PAYMENTS, p=PAYMENT_W)
        status = rng.choice(STATUS, p=STATUS_W)

        is_bf = date.month == 11 and date.day >= 20
        disc_opts = [0, 5, 10, 15, 20, 30, 40] if is_bf else [0, 0, 0, 5, 10, 15, 20]
        discount = int(rng.choice(disc_opts))

        shipping = SHIPPING_BASE[cust["state"]] + rng.normal(0, 3)
        shipping = round(max(shipping, 0), 2)
        if rng.random() < 0.18:  # frete grátis em parte dos pedidos
            shipping = 0.0

        n_items = int(rng.choice([1, 2, 3], p=[0.62, 0.28, 0.10]))
        prod_idx = rng.choice(len(CATALOG), size=n_items, replace=False, p=pop)

        for pi in prod_idx:
            cat, name, price, cost_ratio = CATALOG[pi]
            # preço varia levemente ao longo do tempo (reajustes)
            years = (date - pd.Timestamp(START)).days / 365
            unit_price = round(price * (1 + 0.04 * years), 2)
            rows.append(
                {
                    "order_id": order_id,
                    "order_date": date,
                    "customer_id": cust["customer_id"],
                    "customer_name": cust["customer_name"],
                    "email": cust["email"],
                    "state": cust["state"],
                    "city": cust["city"],
                    "product_id": f"P{pi + 1:03d}",
                    "product_name": name,
                    "category": cat,
                    "quantity": int(rng.choice([1, 1, 1, 2, 2, 3], ))
                    if price < 300 else int(rng.choice([1, 1, 1, 1, 2])),
                    "unit_price": unit_price,
                    "unit_cost": round(unit_price * cost_ratio, 2),
                    "discount_pct": discount,
                    "shipping_fee": shipping if pi == prod_idx[0] else 0.0,
                    "payment_method": payment,
                    "channel": channel,
                    "status": status,
                }
            )
    return pd.DataFrame(rows)


def _customer_weights(n):
    """Alguns clientes compram muito mais (cauda longa, como na vida real)."""
    w = rng.pareto(2.5, size=n) + 1
    return w / w.sum()


# ----------------------------------------------------------------------
# 6. Sujeira proposital
# ----------------------------------------------------------------------
def make_dirty(df):
    df = df.copy()
    n = len(df)

    # 6.1 Datas em formatos mistos (vira texto)
    fmt_choice = rng.choice(["iso", "br", "dash"], size=n, p=[0.80, 0.14, 0.06])
    dates = []
    for d, f in zip(df["order_date"], fmt_choice):
        if f == "iso":
            dates.append(d.strftime("%Y-%m-%d"))
        elif f == "br":
            dates.append(d.strftime("%d/%m/%Y"))
        else:
            dates.append(d.strftime("%d-%m-%Y"))
    df["order_date"] = dates

    # 6.2 Categorias escritas de várias formas
    def mess_category(c):
        r = rng.random()
        if r < 0.80:
            return c
        if r < 0.88:
            return c.lower()
        if r < 0.94:
            return c.upper()
        if r < 0.97:
            return " " + c + " "
        return c.replace("ô", "o").replace("ç", "c").replace("ã", "a").replace("é", "e")

    df["category"] = df["category"].apply(mess_category)

    # 6.3 Estados: sigla minúscula ou nome por extenso
    state_names = {"SP": "São Paulo", "RJ": "Rio de Janeiro", "MG": "Minas Gerais"}
    def mess_state(s):
        r = rng.random()
        if r < 0.90:
            return s
        if r < 0.96:
            return s.lower()
        return state_names.get(s, s)

    df["state"] = df["state"].apply(mess_state)

    # 6.4 Preço unitário como texto em formato brasileiro (~3% das linhas)
    df["unit_price"] = df["unit_price"].astype(object)
    mask = rng.random(n) < 0.03
    df.loc[mask, "unit_price"] = df.loc[mask, "unit_price"].apply(
        lambda v: "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )

    # 6.5 Nulos
    for col, frac in [("email", 0.04), ("payment_method", 0.02),
                      ("city", 0.03), ("channel", 0.015), ("discount_pct", 0.02)]:
        df.loc[rng.random(n) < frac, col] = np.nan

    # 6.6 Alguns outliers de quantidade (erro de digitação)
    out_idx = rng.choice(n, size=12, replace=False)
    df.loc[out_idx, "quantity"] = rng.choice([50, 99, 100], size=12)

    # 6.7 Linhas duplicadas (~1,5%)
    dups = df.sample(frac=0.015, random_state=SEED)
    df = pd.concat([df, dups], ignore_index=True)

    # embaralha para não ficar tudo ordenado
    return df.sample(frac=1, random_state=SEED).reset_index(drop=True)


# ----------------------------------------------------------------------
def main():
    root = Path(__file__).resolve().parent.parent
    out_dir = root / "data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Gerando vendas...")
    clean = build_sales()
    print(f"  linhas limpas: {len(clean):,}")

    dirty = make_dirty(clean)
    print(f"  linhas após sujeira (com duplicatas): {len(dirty):,}")

    csv_path = out_dir / "vendas_raw.csv"
    xlsx_path = out_dir / "vendas_raw.xlsx"
    dirty.to_csv(csv_path, index=False, encoding="utf-8")
    dirty.to_excel(xlsx_path, index=False)

    print(f"Salvo em:\n  {csv_path}\n  {xlsx_path}")
    print("\nPrévia:")
    print(dirty.head())


if __name__ == "__main__":
    main()
