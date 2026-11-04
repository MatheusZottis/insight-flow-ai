# Insight Flow AI

Pipeline de dados e dashboard web interativo para análise de vendas de e-commerce. O projeto recebe uma base bruta (com os problemas típicos de dados reais), limpa e organiza, calcula os indicadores de negócio e apresenta tudo em um dashboard personalizável com insights automáticos.

**Dashboard online:** https://matheuszottis.github.io/insight-flow-ai/

> A base de dados é **fictícia**, gerada por script para simular uma loja de e-commerce brasileira (cerca de 13 mil linhas de vendas, de 2024 a 2025).

![Dashboard no tema escuro](docs/tema-escuro.png)

## O que o projeto faz

1. **Gera uma base realista e "suja"**: datas em vários formatos, categorias escritas de formas diferentes, valores monetários em texto, campos vazios, quantidades absurdas e linhas duplicadas.
2. **Limpa e padroniza** os dados, recuperando informações faltantes quando possível, e gera um relatório do que foi corrigido.
3. **Calcula os indicadores**: receita, lucro, margem, ticket médio, taxas de cancelamento e devolução, crescimento anual, rankings e cortes por categoria, região, canal e dia da semana.
4. **Apresenta em um dashboard web** com gráficos interativos, insights automáticos e 6 temas visuais.

## Temas

O visual é totalmente personalizável via variáveis CSS. O dashboard vem com 6 temas: Escuro, Claro, Oceano, Corporativo, Floresta e Pôr do sol.

| Oceano | Corporativo |
|---|---|
| ![Tema Oceano](docs/tema-oceano.png) | ![Tema Corporativo](docs/tema-corporativo.png) |

## Relatório de limpeza

![Relatório de limpeza](docs/relatorio-limpeza.png)

## Tecnologias

- **Python** e **pandas**: geração, limpeza e análise dos dados
- **HTML, CSS e JavaScript**: interface do dashboard
- **Plotly**: gráficos interativos
- **GitHub Pages**: publicação

## Estrutura do projeto

```
insight-flow-ai/
├── data/
│   ├── raw/            # base original (suja)
│   └── processed/      # base limpa, relatório e indicadores
├── src/
│   ├── generate_data.py   # gera a base fictícia
│   ├── cleaning.py        # limpeza e colunas derivadas
│   └── kpis.py            # cálculo dos indicadores
├── web/                # dashboard (HTML, CSS, JS)
├── docs/               # imagens do README
└── requirements.txt
```

## Como rodar

Requer Python 3.10 ou superior.

```powershell
# 1. Criar e ativar o ambiente virtual
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Instalar as dependências
pip install -r requirements.txt

# 3. Rodar o pipeline, na ordem
python src/generate_data.py
python src/cleaning.py
python src/kpis.py
```

Depois, abra `web/index.html` no navegador.

## Regras de negócio

- Receita, lucro e ticket médio consideram apenas pedidos com status **Entregue**.
- Pedidos **Cancelados** e **Devolvidos** entram somente nas taxas de perda.
- Receita líquida = valor bruto menos desconto. O frete não entra na receita.
- Quantidades acima de 20 unidades por item são tratadas como erro de digitação.

## Roadmap

- [x] Pipeline de limpeza e indicadores
- [x] Dashboard web com temas
- [ ] Versão em Power BI
- [ ] Upload de planilhas pelo usuário (qualquer Excel ou CSV)
- [ ] Insights escritos por IA (Claude API)

## Autor

**Matheus Zottis**: [GitHub](https://github.com/MatheusZottis)
