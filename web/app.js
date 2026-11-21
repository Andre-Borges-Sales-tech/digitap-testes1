"use strict";
const app = document.querySelector("#app");
const names = { ana: "Ana · Horta A", lucia: "Lúcia · Horta B" };
const owner = {
  oferta: "ana",
  proposta: "lucia",
  correcao: "ana",
  decisao: "lucia",
  publicar: "lucia",
  retirar: "lucia",
};
const titles = {
  oferta: "Registrar oferta de transporte",
  proposta: "Registrar proposta inicial",
  correcao: "Corrigir frequência do transporte",
  decisao: "Registrar decisão das duas hortas",
  publicar: "Autorizar pedido público",
  retirar: "Pedido de apoio publicado",
};
const labels = {
  frequencia: "Frequência do transporte",
  prioridade: "Prioridade",
  motivo: "Motivo registrado na devolutiva",
  acao: "Próxima ação acordada",
  pedido: "Texto exato que visitantes poderão ler",
};
const examples = {
  oferta: { frequencia: "Todo sábado" },
  proposta: { prioridade: "Oficina de mudas" },
  correcao: {
    frequencia: "Um sábado por mês",
    motivo: "Ana conferiu o calendário do transporte na devolutiva.",
  },
  decisao: {
    prioridade: "Irrigação irregular",
    acao: "Buscar apoio para avaliar a irrigação irregular.",
    motivo:
      "As duas hortas identificaram a irregularidade da irrigação como prioridade.",
  },
  publicar: {
    pedido: "Buscamos apoio para avaliar a irrigação das hortas comunitárias.",
  },
  retirar: {},
};
const copy = {
  oferta: "Registre a disponibilidade que Ana informou durante a roda.",
  proposta: "Registre a primeira proposta levantada por Lúcia.",
  correcao:
    "Ana conferiu sua disponibilidade. Registre a correção e a razão da mudança.",
  decisao:
    "Lúcia registra o que as duas hortas decidiram e qual será a próxima ação.",
  publicar:
    "Antes de autorizar, confira a próxima ação e a frequência do transporte no plano. Apenas o texto deste pedido será exibido aos visitantes.",
  retirar:
    "Confira o resultado na visão de visitante. Você também pode retirar a autorização.",
};
const escapeHtml = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (ch) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        ch
      ],
  );
const date = (value) => new Date(value).toLocaleString("pt-BR");
let current = null,
  actor = "ana",
  message = "",
  isError = false;
async function api(path, body) {
  const options = { cache: "no-store", credentials: "same-origin" };
  if (body !== undefined)
    Object.assign(options, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Hortas": "1" },
      body: JSON.stringify(body),
    });
  const res = await fetch(path, options);
  const data = await res.json();
  if (!res.ok)
    throw Object.assign(new Error(data.erro || "Falha na consulta."), {
      status: res.status,
    });
  return data;
}
function alertText(value, error = false) {
  message = value;
  isError = error;
  const el = document.getElementById("feedback");
  if (el) {
    el.textContent = value;
    el.classList.toggle("error", error);
  }
}
const feedback = () =>
  '<div role="status" aria-live="polite" class="feedback' +
  (isError ? " error" : "") +
  '" id="feedback">' +
  escapeHtml(message) +
  "</div>";
function login() {
  current = null;
  app.innerHTML =
    '<div class="hero"><p class="eyebrow">Experimento participativo</p><h1>Duas hortas</h1><p class="sub">Registre uma roda de escuta e acompanhe como as decisões mudam na devolutiva.</p></div><section class="card narrow"><h2>Entrada do facilitador</h2><p>Use a chave exibida no terminal ao iniciar o laboratório.</p>' +
    feedback() +
    '<form id="login"><label class="field"><span>Chave do facilitador</span><input name="chave" type="password" autocomplete="off" required></label><div class="buttons"><button>Entrar no laboratório</button></div></form></section>';
  document.getElementById("login").onsubmit = async (e) => {
    e.preventDefault();
    const f = e.currentTarget;
    try {
      await api("/api/entrar", { chave: f.elements.chave.value.trim() });
      await openHome();
    } catch (err) {
      alertText(err.message, true);
    }
  };
}
async function openHome() {
  const rounds = await api("/api/rodadas");
  current = null;
  alertText("");
  app.innerHTML =
    '<div class="hero spread"><div><p class="eyebrow">Experimento participativo</p><h1>Duas hortas</h1><p class="sub">Simule os papéis de Ana e Lúcia, revise o plano e confira o pedido público.</p></div><button id="new">Iniciar nova rodada</button></div>' +
    feedback() +
    '<section class="card"><h2>Suas rodadas</h2>' +
    (rounds.length
      ? '<ul class="rounds">' +
        rounds
          .map(
            (r) =>
              '<li><button class="secondary" data-id="' +
              r.id +
              '"><span>Rodada ' +
              r.numero +
              "</span><small>" +
              escapeHtml(date(r.criada)) +
              "</small></button></li>",
          )
          .join("") +
        "</ul>"
      : "<p>Inicie a primeira rodada para registrar a oferta de Ana.</p>") +
    "</section>";
  document.getElementById("new").onclick = async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    try {
      const { id } = await api("/api/rodadas", {});
      await openRound(id);
    } catch (err) {
      alertText(err.message, true);
      btn.disabled = false;
    }
  };
  app
    .querySelectorAll("[data-id]")
    .forEach(
      (b) =>
        (b.onclick = () =>
          openRound(b.dataset.id).catch((err) => alertText(err.message, true))),
    );
}
async function openRound(id) {
  current = await api("/api/rodadas/" + id);
  actor = owner[current.proximo];
  alertText("");
  render();
}
function historyEntry(event) {
  const d = event.dados;
  const facts = [];
  if (d.antes) facts.push(["Anterior", d.antes]);
  for (const key of [
    "frequencia",
    "prioridade",
    "acao",
    "motivo",
    "pedido",
    "decidido_por",
  ])
    if (d[key])
      facts.push([
        key === "decidido_por"
          ? "Decisão de"
          : key === "pedido"
            ? "Texto autorizado"
            : labels[key],
        d[key],
      ]);
  const name = {
    oferta: "Oferta de transporte",
    proposta: "Proposta inicial",
    correcao: "Transporte corrigido",
    decisao: "Prioridade revista",
    publicar: "Divulgação autorizada",
    retirar: "Divulgação retirada",
  }[event.tipo];
  return (
    '<article class="event" id="v' +
    event.versao +
    '"><small>v' +
    event.versao +
    " · " +
    escapeHtml(date(event.registrado)) +
    "</small><h3>" +
    name +
    "</h3><p>Registro de <b>" +
    names[event.autor] +
    "</b></p>" +
    facts
      .map(([k, v]) => "<p><b>" + k + "</b> · " + escapeHtml(v) + "</p>")
      .join("") +
    "</article>"
  );
}
function plano(p) {
  const source = (n) =>
    n ? ' <a class="meta" href="#v' + n + '">origem v' + n + "</a>" : "";
  return (
    '<aside><section class="card plan"><p class="eyebrow">Versão em vigor</p><h2>Plano da rodada</h2><dl><dt>Prioridade ' +
    source(p.origem_prioridade) +
    "</dt><dd>" +
    escapeHtml(p.prioridade || "A registrar") +
    "</dd><dt>Transporte " +
    source(p.origem_transporte) +
    "</dt><dd>" +
    escapeHtml(p.frequencia || "A registrar") +
    "</dd><dt>Próxima ação " +
    source(p.acao ? p.origem_prioridade : null) +
    "</dt><dd>" +
    escapeHtml(p.acao || "A combinar na devolutiva") +
    '</dd></dl></section><section class="card outline"><h3>Visão de visitante</h3><p>' +
    (current.pedido
      ? "Há um pedido autorizado."
      : "Ainda não há pedido publicado.") +
    '</p><a class="button secondary" href="/p/' +
    current.id +
    '" target="_blank" rel="noopener">Abrir página pública ↗</a></section></aside>'
  );
}
function inputForm(t) {
  if (actor !== owner[t])
    return (
      '<p class="note">Para continuar, selecione ' + names[owner[t]] + ".</p>"
    );
  const keys = Object.keys(examples[t]);
  const prev =
    t === "correcao"
      ? current.plano.frequencia
      : t === "decisao"
        ? current.plano.prioridade
        : null;
  const agree = {
    decisao: "Confirmo que registro a decisão conjunta das hortas A e B.",
    publicar:
      "As duas hortas autorizam a divulgação somente do texto deste pedido.",
    retirar: "As duas hortas decidiram retirar o pedido da página pública.",
  }[t];
  return (
    '<form id="entry">' +
    (prev
      ? '<p class="note"><b>Versão anterior</b> · ' + escapeHtml(prev) + "</p>"
      : "") +
    (t === "retirar"
      ? '<p class="note">' + escapeHtml(current.pedido) + "</p>"
      : "") +
    keys
      .map(
        (k) =>
          '<label class="field"><span>' +
          labels[k] +
          '</span><textarea name="' +
          k +
          '" maxlength="500" required></textarea></label>',
      )
      .join("") +
    (agree
      ? '<label class="check"><input type="checkbox" name="confirmado" required><span>' +
        agree +
        "</span></label>"
      : "") +
    '<div class="buttons"><button type="submit">' +
    ({
      publicar: "Publicar pedido autorizado",
      retirar: "Retirar pedido",
      decisao: "Salvar decisão conjunta",
    }[t] || "Salvar registro") +
    "</button>" +
    (keys.length
      ? '<button type="button" class="text-link" id="example">Preencher exemplo</button>'
      : "") +
    "</div></form>"
  );
}
function render() {
  const r = current,
    t = r.proximo;
  const st = r.versao < 2 ? 0 : r.versao < 4 ? 1 : r.pedido ? 3 : 2;
  app.innerHTML =
    '<div class="hero"><button class="text-link" id="home">← Todas as rodadas</button><p class="eyebrow">Caderno de campo · Rodada ' +
    r.numero +
    '</p><h1>Duas hortas</h1></div><ol class="stagebar">' +
    ["Roda de escuta", "Devolutiva", "Conferir o plano", "Divulgação"]
      .map(
        (s, i) =>
          '<li class="' +
          (i < st ? "done" : i === st ? "active" : "") +
          '"' +
          (i === st ? ' aria-current="step"' : "") +
          ">" +
          s +
          "</li>",
      )
      .join("") +
    "</ol>" +
    feedback() +
    '<div class="grid"><div><section class="card"><p class="step">Registro interno</p><h2>' +
    titles[t] +
    "</h2><p>" +
    copy[t] +
    '</p><span class="roles-caption">Simular participante</span><div class="roles">' +
    Object.entries(names)
      .map(
        ([id, name]) =>
          '<button class="role" data-role="' +
          id +
          '" aria-pressed="' +
          (id === actor) +
          '">' +
          name +
          "</button>",
      )
      .join("") +
    "</div>" +
    inputForm(t) +
    "</section></div>" +
    plano(r.plano) +
    '</div><section class="card"><p class="eyebrow">Memória interna</p><h2>Histórico da rodada</h2>' +
    (r.eventos.length
      ? r.eventos.slice().reverse().map(historyEntry).join("")
      : "<p>Ainda não há registros.</p>") +
    "</section>";
  document.getElementById("home").onclick = () =>
    openHome().catch((err) => alertText(err.message, true));
  app.querySelectorAll("[data-role]").forEach(
    (b) =>
      (b.onclick = () => {
        if (b.dataset.role !== actor) {
          actor = b.dataset.role;
          alertText("");
          render();
        }
      }),
  );
  const form = document.getElementById("entry");
  if (!form) return;
  const sample = document.getElementById("example");
  if (sample)
    sample.onclick = () => {
      for (const [k, v] of Object.entries(examples[t]))
        if (!form.elements[k].value.trim()) form.elements[k].value = v;
    };
  form.onsubmit = async (e) => {
    e.preventDefault();
    const controls = app.querySelectorAll("button,textarea,input");
    controls.forEach((control) => {
      control.disabled = true;
    });
    const payload = { tipo: t, autor: actor, versao: r.versao };
    for (const k of Object.keys(examples[t]))
      payload[k] = form.elements[k].value;
    if (form.elements.confirmado)
      payload.confirmado = form.elements.confirmado.checked;
    try {
      current = await api("/api/rodadas/" + r.id, payload);
      actor = owner[current.proximo];
      alertText(
        t === "retirar"
          ? "Autorização retirada."
          : t === "publicar"
            ? "Pedido publicado. Confira a página de visitante."
            : "Registro salvo no histórico.",
      );
      render();
    } catch (err) {
      if (err.status === 409) {
        await openRound(r.id).catch(() => {});
      }
      if (err.status === 401) {
        login();
      }
      alertText(err.message, true);
      controls.forEach((control) => {
        control.disabled = false;
      });
    }
  };
}
(async () => {
  try {
    const hash = new URLSearchParams(location.hash.slice(1));
    if (hash.has("chave")) {
      history.replaceState(null, "", location.pathname);
      await api("/api/entrar", { chave: hash.get("chave") });
    }
    await openHome();
  } catch (err) {
    if (err.status !== 401) alertText(err.message, true);
    login();
  } finally {
    app.setAttribute("aria-busy", "false");
  }
})();
