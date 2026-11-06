"""
run.py
Roda o pipeline completo para UM cliente: lê a planilha, limpa, calcula os
indicadores e monta a pasta de entrega com o dashboard pronto.

Uso (na raiz do projeto):
    python src/run.py --arquivo data/raw/vendas_raw.csv --config config/loja_demo.json
    python src/run.py --arquivo ... --config ... --ia      (com insights da Claude API)

Saída (em saida/<nome-do-cliente>/):
    dashboard/   -> abrir index.html; é isso que vai para o cliente
    dados/       -> base limpa, relatório de limpeza e indicadores
"""

import argparse
import json
import re
import shutil
import unicodedata
from pathlib import Path

import pandas as pd

from cleaning import clean, print_report
from kpis import compute_kpis, print_summary

ROOT = Path(__file__).resolve().parent.parent
WEB_TEMPLATE = ["index.html", "style.css", "script.js"]


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "cliente"


def read_input(path: Path, cfg: dict) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        return pd.read_excel(path, sheet_name=cfg.get("aba", 0))
    for enc in ("utf-8-sig", "latin-1"):   # CSV: detecta o separador (, ou ;) sozinho
        try:
            return pd.read_csv(path, sep=None, engine="python", encoding=enc)
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"Não consegui ler o arquivo: {path}")


def json_default(o):
    return o.item() if hasattr(o, "item") else str(o)


def main():
    ap = argparse.ArgumentParser(description="Insight Flow AI: pipeline por cliente")
    ap.add_argument("--arquivo", required=True, help="planilha do cliente (.xlsx, .xls ou .csv)")
    ap.add_argument("--config", required=True, help="arquivo de configuração do cliente (.json)")
    ap.add_argument("--saida", help="pasta de saída (padrão: saida/<cliente>)")
    ap.add_argument("--ia", action="store_true", help="gera insights escritos com a Claude API (opcional)")
    ap.add_argument("--ia-simulada", action="store_true",
                    help="preenche o card de IA com textos de exemplo, sem API (só para testar o visual)")
    ap.add_argument("--estimar-custo", action="store_true",
                    help="estima o custo da IA por relatório, sem chamar a API (não precisa de chave)")
    ap.add_argument("--modelo", default="claude-haiku-5-5", help="modelo da Claude API usado com --ia")
    args = ap.parse_args()

    arquivo, config = Path(args.arquivo), Path(args.config)
    for p in (arquivo, config):
        if not p.exists():
            raise SystemExit(f"Arquivo não encontrado: {p}")

    cfg = json.loads(config.read_text(encoding="utf-8"))
    raw = read_input(arquivo, cfg)
    print(f"Planilha lida: {len(raw):,} linhas, {len(raw.columns)} colunas")

    try:
        df, report = clean(raw, cfg)
    except ValueError as e:
        raise SystemExit(f"\nERRO: {e}")
    print_report(report)

    kpis = compute_kpis(df, cfg)
    print_summary(kpis)

    if args.estimar_custo:   # não gasta nada: só calcula o tamanho do prompt
        from insights_ia import estimar_custo
        e = estimar_custo(kpis, args.modelo)
        print("ESTIMATIVA DE CUSTO DA IA (por relatório)")
        print("-" * 52)
        print(f"Modelo: {e['modelo']}")
        print(f"Entrada: ~{e['entrada']:,} tokens | Saída: até {e['saida_max']:,} tokens")
        print(f"Custo máximo estimado: US$ {e['custo_usd']:.4f} por relatório\n")

    if args.ia:   # camada opcional: só roda com --ia e chave no .env
        try:
            from insights_ia import gerar_insights
            textos, uso = gerar_insights(kpis, args.modelo)
            kpis["insights_ia"] = textos
            print("INSIGHTS POR IA")
            print("-" * 52)
            for t in textos:
                print(f"- {t}\n")
            print(f"(modelo {uso['modelo']}: {uso['entrada']:,} tokens de entrada, {uso['saida']:,} de saída)\n")
        except Exception as e:   # a entrega não pode travar por causa da IA
            print(f"\nAVISO: não foi possível gerar os insights por IA ({e}).")
            print("O dashboard será gerado normalmente, sem eles.\n")

    elif args.ia_simulada:
        ex = ["Texto de EXEMPLO: aqui a IA vai escrever análises e sugestões a partir dos números do cliente."]
        c = kpis.get("crescimento_anual")
        if c and c["receita_pct"] is not None:
            ex.append(f"A receita variou {c['receita_pct']}% de {c['ano_anterior']} para {c['ano_atual']}. "
                      "Vale entender o que puxou esse resultado e repetir o que funcionou.")
        if kpis.get("por_categoria"):
            cat = kpis["por_categoria"][0]
            ex.append(f"{cat['category']} concentra {cat['participacao_pct']}% da receita. Pode indicar dependência "
                      "de uma categoria: vale investigar se há espaço para impulsionar as demais.")
        kpis["insights_ia"], kpis["insights_ia_simulada"] = ex, True

    out = Path(args.saida) if args.saida else ROOT / "saida" / slug(cfg.get("cliente", "cliente"))
    dados, dash = out / "dados", out / "dashboard"
    dados.mkdir(parents=True, exist_ok=True)
    dash.mkdir(parents=True, exist_ok=True)

    df.to_csv(dados / "vendas_clean.csv", index=False, encoding="utf-8")
    (dados / "relatorio_limpeza.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")
    kpis_json = json.dumps(kpis, ensure_ascii=False, default=json_default)
    (dados / "kpis.json").write_text(kpis_json, encoding="utf-8")

    for name in WEB_TEMPLATE:   # copia o dashboard-modelo (pasta web/)
        shutil.copy(ROOT / "web" / name, dash / name)
    (dash / "kpis_data.js").write_text("window.KPIS = " + kpis_json + ";", encoding="utf-8")

    print(f"Pasta de entrega pronta em: {out}")
    print(f"Abra: {dash / 'index.html'}")


if __name__ == "__main__":
    main()