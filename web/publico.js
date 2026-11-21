"use strict";
(async () => {
  const area = document.getElementById("pedido");
  try {
    const id = location.pathname.split("/").pop();
    const response = await fetch("/api/publico/" + id, {
      credentials: "same-origin",
      cache: "no-store",
    });
    if (!response.ok) throw Error();
    const { pedido } = await response.json();
    area.textContent = pedido ?? "Nenhum pedido de apoio publicado.";
  } catch {
    area.textContent =
      "A consulta está indisponível. Atualize a página para tentar novamente.";
  }
})();
