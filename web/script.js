// Insight Flow AI: dashboard de vendas
// Lê window.KPIS (gerado por src/kpis.py em web/kpis_data.js)

const K = window.KPIS;
const $ = (id) => document.getElementById(id);

// ---------- Formatação ----------
const brl = (v) => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const brl2 = (v) => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const num = (v) => v.toLocaleString("pt-BR");
const pt = (v) => v.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const DIAS = { Monday: "Seg", Tuesday: "Ter", Wednesday: "Qua", Thursday: "Qui", Friday: "Sex", Saturday: "Sáb", Sunday: "Dom" };
const mesLabel = (ym) => { const [y, m] = ym.split("-"); return `${MESES[+m - 1]}/${y.slice(2)}`; };

// ---------- Temas ----------
const THEMES = [
  ["dark", "Escuro", "#7c8cff"], ["light", "Claro", "#3b6cff"], ["ocean", "Oceano", "#5ee7ff"],
  ["corporate", "Corporativo", "#1f3a5f"], ["forest", "Floresta", "#7bd88f"], ["sunset", "Pôr do sol", "#ffb347"],
];
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const alpha = (hex, a) => { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; };

function setTheme(t) {
  document.documentElement.dataset.theme = t;
  try { localStorage.setItem("insightful-theme", t); } catch (e) { /* ignora */ }
  document.querySelectorAll("#themes button").forEach((b) => b.classList.toggle("on", b.dataset.t === t));
  if (K) drawCharts(); // os gráficos leem as cores do tema atual
}

function buildThemeButtons() {
  $("themes").innerHTML = THEMES.map(
    ([id, nome, cor]) => `<button data-t="${id}" title="${nome}"><i style="background:${cor}"></i>${nome}</button>`
  ).join("");
  $("themes").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (b) setTheme(b.dataset.t);
  });
}

// ---------- Cartões de indicadores ----------
function renderKpis() {
  const g = K.geral, s = K.status, c = K.crescimento_anual || {};
  const items = [
    ["Receita líquida", brl(g.receita_liquida), c.receita_pct],
    g.lucro != null && ["Lucro", brl(g.lucro), c.lucro_pct, `Margem de ${pt(g.margem_pct)}%`],
    ["Pedidos", num(g.pedidos), c.pedidos_pct],
    ["Ticket médio", brl2(g.ticket_medio), c.ticket_medio_pct],
    s && ["Cancelamento", `${pt(s.taxa_cancelamento_pct)}%`, null, "dos pedidos"],
    s && ["Devolução", `${pt(s.taxa_devolucao_pct)}%`, null, "dos pedidos"],
  ].filter(Boolean);
  $("kpis").innerHTML = items.map(([label, valor, delta, sub]) => {
    const d = delta == null ? "" :
      `<span class="delta ${delta >= 0 ? "pos" : "neg"}">${delta >= 0 ? "▲" : "▼"} ${pt(Math.abs(delta))}% vs ${c.ano_anterior}</span>`;
    return `<div class="card kpi"><div class="label">${label}</div><div class="value">${valor}</div>${d}<div class="sub">${sub || ""}</div></div>`;
  }).join("");
}

// ---------- Insights automáticos (regras) ----------
function renderInsights() {
  const g = K.geral, c = K.crescimento_anual, out = [];
  const best = [...K.mensal].sort((a, b) => b.receita - a.receita)[0];
  const media = g.receita_liquida / K.mensal.length;
  out.push(`O melhor mês foi <b>${mesLabel(best.year_month)}</b>, com ${brl(best.receita)} em receita, cerca de ${pt(best.receita / media)}x a média mensal.`);

  if (c && c.receita_pct != null) {
    out.push(`A receita ${c.receita_pct >= 0 ? "cresceu" : "caiu"} <b>${pt(Math.abs(c.receita_pct))}%</b> de ${c.ano_anterior} para ${c.ano_atual}, e os pedidos variaram ${pt(c.pedidos_pct)}%.`);
  }
  const cat = K.por_categoria && K.por_categoria[0];
  if (cat) {
    let t = `<b>${cat.category}</b> lidera em receita (${pt(cat.participacao_pct)}% do total).`;
    if (cat.margem_pct != null) {
      const mm = [...K.por_categoria].sort((a, b) => b.margem_pct - a.margem_pct)[0];
      t += ` A maior margem está em <b>${mm.category}</b> (${pt(mm.margem_pct)}%).`;
    }
    out.push(t);
  }
  const reg = K.por_regiao && K.por_regiao[0];
  if (reg) out.push(`A região <b>${reg.region}</b> concentra ${pt(reg.participacao_pct)}% da receita; as demais regiões são oportunidade de expansão.`);

  const canal = K.por_canal && K.por_canal[0];
  if (canal) out.push(`O canal <b>${canal.channel}</b> é o principal, com ${pt(canal.participacao_pct)}% das vendas.`);

  const perda = K.perda_por_categoria && K.perda_por_categoria[0];
  if (perda) out.push(`<b>${perda.category}</b> tem a maior taxa de cancelamento + devolução (${pt(perda.taxa_problema_pct)}%): vale investigar a causa.`);

  if (K.recorrencia) out.push(`Só <b>${pt(K.recorrencia.taxa_recompra_pct)}%</b> dos clientes compraram mais de uma vez, o que indica espaço para ações de fidelização.`);
  $("insights").innerHTML = out.map((t) => `<li>${t}</li>`).join("");
}

// ---------- Gráficos ----------
const CFG = { displayModeBar: false, responsive: true };

function baseLayout(extra = {}) {
  const grid = alpha(css("--text").startsWith("#") ? css("--text") : "#888888", 0.12);
  return Object.assign({
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: css("--text"), family: "Segoe UI, system-ui, sans-serif", size: 12 },
    margin: { l: 50, r: 12, t: 6, b: 36 },
    xaxis: { gridcolor: grid, zerolinecolor: grid, automargin: true },
    yaxis: { gridcolor: grid, zerolinecolor: grid, automargin: true },
    showlegend: false,
  }, extra);
}
const palette = () => [1, 2, 3, 4, 5, 6].map((i) => css(`--c${i}`));

function barH(id, rows, labelKey, valueKey, color) {
  const d = [...rows].reverse();
  Plotly.react(id, [{
    type: "bar", orientation: "h", x: d.map((r) => r[valueKey]), y: d.map((r) => r[labelKey]),
    text: d.map((r) => brl(r[valueKey])), hovertemplate: "%{y}<br>%{text}<extra></extra>",
    marker: { color },
  }], baseLayout(), CFG);
}

function barV(id, labels, values, colors) {
  Plotly.react(id, [{
    type: "bar", x: labels, y: values, text: values.map(brl),
    hovertemplate: "%{x}<br>%{text}<extra></extra>", marker: { color: colors },
  }], baseLayout({ margin: { l: 56, r: 8, t: 4, b: 28 } }), CFG);
}

// Mostra/esconde o gráfico (e o card) conforme o dado existe; devolve se existe
function toggle(id, data) {
  const el = $(id), card = el.closest(".card");
  const multi = card.querySelectorAll(".chart").length > 1;
  const alvo = multi ? [el, el.previousElementSibling] : [card];
  alvo.forEach((t) => (t.style.display = data ? "" : "none"));
  return !!data;
}

function drawCharts() {
  const p = palette(), m = $("metric").value, d = K.mensal;
  const fmt = m === "pedidos" ? num : brl;

  Plotly.react("ch-mensal", [{
    type: "scatter", mode: "lines+markers", x: d.map((r) => mesLabel(r.year_month)), y: d.map((r) => r[m]),
    text: d.map((r) => fmt(r[m])), hovertemplate: "%{x}<br>%{text}<extra></extra>",
    fill: "tozeroy", fillcolor: alpha(p[0], 0.18), line: { color: p[0], width: 3, shape: "spline" }, marker: { size: 6 },
  }], baseLayout(), CFG);

  if (toggle("ch-cat", K.por_categoria)) barH("ch-cat", K.por_categoria, "category", "receita", p[0]);
  if (toggle("ch-prod", K.top_produtos_receita)) barH("ch-prod", K.top_produtos_receita, "product_name", "receita", p[1]);

  if (toggle("ch-reg", K.por_regiao)) Plotly.react("ch-reg", [{
    type: "pie", hole: 0.55, labels: K.por_regiao.map((r) => r.region), values: K.por_regiao.map((r) => r.receita),
    text: K.por_regiao.map((r) => brl(r.receita)), hovertemplate: "%{label}<br>%{text}<extra></extra>",
    marker: { colors: p, line: { color: "rgba(0,0,0,0)" } }, textinfo: "label+percent",
  }], baseLayout({ margin: { l: 10, r: 10, t: 10, b: 10 } }), CFG);

  if (toggle("ch-canal", K.por_canal)) barV("ch-canal", K.por_canal.map((r) => r.channel), K.por_canal.map((r) => r.receita), p);
  barV("ch-dia", K.por_dia_semana.map((r) => DIAS[r.weekday]), K.por_dia_semana.map((r) => r.receita), p[2]);
}

// ---------- Início ----------
function init() {
  buildThemeButtons();
  if (!K) {
    $("kpis").innerHTML = '<div class="card">Dados não encontrados. Rode <code>python src/kpis.py</code> e recarregue a página.</div>';
    setTheme(document.documentElement.dataset.theme);
    return;
  }
  $("periodo").textContent = `${K.cliente ? K.cliente + " · " : ""}Vendas · ${K.periodo.inicio} a ${K.periodo.fim}`;
  renderKpis();
  renderInsights();
  if (K.geral.lucro == null) $("metric").querySelector('option[value="lucro"]').remove();
  $("metric").addEventListener("change", drawCharts);
  let saved = null;
  try { saved = localStorage.getItem("insightful-theme"); } catch (e) { /* ignora */ }
  setTheme(THEMES.some((t) => t[0] === saved) ? saved : "dark");
}
init();