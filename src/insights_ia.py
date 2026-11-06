"""
insights_ia.py
Gera insights escritos pela Claude API a partir dos indicadores já calculados.

Privacidade: só números AGREGADOS são enviados (totais por mês, categoria,
região...). A planilha, linhas de pedidos e nomes de clientes nunca saem
da sua máquina.

Opcional: só roda com a flag --ia e com a chave no arquivo .env.
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELO_PADRAO = "claude-haiku-5-5"

SYSTEM = """Você é um analista de dados sênior que escreve para donos de negócio, não para técnicos.
Receberá indicadores de vendas já calculados (em reais) e deve escrever de 5 a 7 insights.

Regras:
- Português do Brasil, linguagem simples e direta.
- Cada insight tem 1 a 2 frases, apoiado em números que estão nos dados.
- Use SOMENTE números presentes nos dados. Nunca invente valores nem calcule projeções.
- Indicadores com valor nulo não existem para este cliente: ignore-os.
- Quando sugerir uma causa, trate como hipótese ("pode indicar", "vale investigar"), nunca como fato.
- Termine cada insight com uma ação prática quando fizer sentido.
- Priorize o que muda decisões: crescimento, concentração, sazonalidade, margem, perdas e recompra.

Responda APENAS com um array JSON de strings, sem texto antes ou depois."""


def resumo_para_ia(k: dict) -> dict:
    """Seleciona e enxuga os indicadores que serão enviados (sem dados pessoais)."""
    cols = ["receita", "pedidos", "lucro", "margem_pct", "ticket_medio", "participacao_pct"]

    def tabela(rows, nome, n=8):
        if not rows:
            return None
        return [{"nome": r[nome], **{c: r[c] for c in cols if r.get(c) is not None}} for r in rows[:n]]

    return {
        "cliente": k.get("cliente"),
        "periodo": k["periodo"],
        "geral": k["geral"],
        "status": k.get("status"),
        "crescimento_anual": k.get("crescimento_anual"),
        "por_ano": k["por_ano"],
        "mensal": [{"mes": r["year_month"], "receita": r["receita"], "pedidos": r["pedidos"]}
                   for r in k["mensal"]],
        "categorias": tabela(k.get("por_categoria"), "category"),
        "regioes": tabela(k.get("por_regiao"), "region"),
        "canais": tabela(k.get("por_canal"), "channel"),
        "top_produtos": tabela(k.get("top_produtos_receita"), "product_name", 5),
        "perda_por_categoria": (k.get("perda_por_categoria") or [])[:5] or None,
        "recorrencia": k.get("recorrencia"),
    }


# Preços em US$ por milhão de tokens (entrada, saída), para prompts de até 100 mil tokens.
# Confira sempre a tabela oficial: platform.claude.com/docs/en/about-claude/pricing
PRECOS = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}


def estimar_custo(kpis: dict, modelo: str = MODELO_PADRAO) -> dict:
    """Estima o custo de UM relatório sem chamar a API (não precisa de chave nem de saldo)."""
    if modelo not in PRECOS:
        raise ValueError(f"sem preço cadastrado para '{modelo}'. Modelos: {', '.join(PRECOS)}")
    texto = SYSTEM + json.dumps(resumo_para_ia(kpis), ensure_ascii=False)
    entrada = round(len(texto) / 2.5)   # ~2,5 caracteres por token: estimativa conservadora
    saida = 1500                        # teto de saída configurado; o uso real costuma ser menor
    p_in, p_out = PRECOS[modelo]
    return {"modelo": modelo, "entrada": entrada, "saida_max": saida,
            "custo_usd": (entrada * p_in + saida * p_out) / 1_000_000}


def _parse(texto: str) -> list:
    t = texto.strip()
    if t.startswith("```"):
        t = t.strip("`").removeprefix("json").strip()
    try:
        dados = json.loads(t)
        if isinstance(dados, list):
            return [str(x).strip() for x in dados if str(x).strip()]
    except json.JSONDecodeError:
        pass
    # plano B: a IA respondeu em texto solto, uma ideia por linha
    linhas = [ln.strip(" -•*\t") for ln in texto.splitlines()]
    return [ln for ln in linhas if len(ln) > 20]


def gerar_insights(kpis: dict, modelo: str = MODELO_PADRAO):
    """Devolve (lista de insights, dict com uso de tokens). Levanta RuntimeError se algo faltar."""
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass   # sem python-dotenv, ainda vale uma variável de ambiente do sistema

    chave = os.getenv("ANTHROPIC_API_KEY")
    if not chave:
        raise RuntimeError("ANTHROPIC_API_KEY não encontrada. Crie o arquivo .env na raiz do projeto.")
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("biblioteca 'anthropic' não instalada (pip install anthropic)")

    client = anthropic.Anthropic(api_key=chave)
    resposta = client.messages.create(
        model=modelo,
        max_tokens=1500,
        system=SYSTEM,
        messages=[{"role": "user",
                   "content": "Indicadores:\n" + json.dumps(resumo_para_ia(kpis), ensure_ascii=False)}],
    )
    texto = "".join(b.text for b in resposta.content if getattr(b, "type", "") == "text")
    uso = {"modelo": modelo, "entrada": resposta.usage.input_tokens, "saida": resposta.usage.output_tokens}
    return _parse(texto), uso