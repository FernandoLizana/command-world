(function () {
  const $ = (id) => document.getElementById(id);
  const overlays = ["onboarding", "hoy", "captura", "lista", "finanzas", "revision", "tablero", "bitacora"];

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[c]);
  }

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }).then((r) => r.json());
  }

  function toast(msg) {
    if (window.DRWorld && window.DRWorld.toast) window.DRWorld.toast(msg);
  }

  function fmtMoney(cents, currency) {
    const n = (Number(cents) || 0) / 100;
    return n.toLocaleString("es", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " " + (currency || "");
  }

  function go(hash) {
    location.hash = hash;
  }

  function loadToday(minutes) {
    const box = $("today-body");
    if (!box) return;
    box.textContent = "Calculando…";
    const q = minutes ? "?minutes=" + minutes : "";
    fetch("/api/today" + q, { credentials: "same-origin" })
      .then((r) => r.json())
      .then(renderToday)
      .catch(() => {
        box.textContent = "No se pudo cargar el turno.";
      });
  }

  function renderToday(data) {
    const box = $("today-body");
    if (!box) return;
    if (data.error) {
      box.textContent = data.error;
      return;
    }
    const items = data.items || [];
    const skipped = data.skipped || [];
    const overload = data.overload_week || {};
    let html = `<p>Presupuesto ${data.minutes || 0} min · usados ${data.used || 0} · quedan ${data.remaining || 0}. Estado: ${data.status || "borrador"}.</p>`;
    if (overload.overload) {
      html += `<p class="muted">Esta semana tiene ${overload.overload} min de sobrecarga (${overload.planned} planificados / ${overload.capacity} de capacidad).</p>`;
    }
    if (!items.length) {
      html += "<p>Ninguna misión cabe en este tiempo. Divide una tarea grande o sube el presupuesto.</p>";
    }
    (data.follow_ups || []).forEach((fu) => {
      html += `<p class="muted">Seguimiento: ${fu.title} · ${fu.reason}</p>`;
    });
    items.forEach((it) => {
      const mins = it.unestimated ? "sin estimar" : (it.minutes || 0) + " min";
      html += `<article class="mission-card">
        <div class="kicker">${it.project || ""} · ${mins}</div>
        <h3>${it.title}</h3>
        <p>${it.reason || ""}</p>
        <div class="row-actions">
          <button class="btn solid" type="button" data-continue="${it.mission_id}">Iniciar</button>
        </div>
      </article>`;
    });
    if (skipped.length) {
      html += "<p class='muted'>Omitidas: " + skipped.map((s) => s.reason).join(" · ") + "</p>";
    }
    box.innerHTML = html;
    box.querySelectorAll("[data-continue]").forEach((btn) => {
      btn.addEventListener("click", () => {
        fetch("/api/missions/" + btn.dataset.continue + "/continue", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: "{}",
        })
          .then((r) => r.json())
          .then((res) => {
            toast(res.completed_mission ? "Misión cumplida." : "Avance registrado.");
            if (window.DRMap && window.DRMap.refresh) window.DRMap.refresh();
            loadToday(data.minutes);
          });
      });
    });
  }

  function loadInbox() {
    const box = $("capture-list");
    if (!box) return;
    fetch("/api/inbox", { credentials: "same-origin" })
      .then((r) => r.json())
      .then((items) => {
        if (!items.length) {
          box.innerHTML = "<p class='muted'>Bandeja vacía.</p>";
          return;
        }
        box.innerHTML = items
          .map(
            (c) => `<article class="mission-card">
              <p>${c.text}</p>
              <div class="row-actions">
                <button class="btn" type="button" data-kind="mission" data-id="${c.id}">Misión</button>
                <button class="btn" type="button" data-kind="note" data-id="${c.id}">Nota</button>
                <button class="btn" type="button" data-kind="opportunity" data-id="${c.id}">Oportunidad</button>
                <button class="btn ghost" type="button" data-kind="later" data-id="${c.id}">Más adelante</button>
              </div>
            </article>`
          )
          .join("");
        box.querySelectorAll("[data-kind]").forEach((btn) => {
          btn.addEventListener("click", () => convertCapture(btn.dataset.id, btn.dataset.kind));
        });
      });
  }

  function convertCapture(id, kind) {
    const needProject = kind === "mission" || kind === "opportunity";
    const run = (projectId) => {
      post("/api/inbox/" + id + "/convert", { kind, project_id: projectId }).then((row) => {
        if (row.error) {
          toast(row.error);
          return;
        }
        toast("Captura procesada.");
        loadInbox();
        if (window.DRMap && window.DRMap.refresh) window.DRMap.refresh();
      });
    };
    if (!needProject) {
      run(null);
      return;
    }
    fetch("/api/projects", { credentials: "same-origin" })
      .then((r) => r.json())
      .then((projects) => {
        if (!projects.length) {
          toast("Crea un edificio (proyecto) primero.");
          return;
        }
        const pick = window.prompt(
          "ID del proyecto:\n" + projects.map((p) => p.id + " · " + p.name).join("\n"),
          String(projects[0].id)
        );
        if (!pick) return;
        run(Number(pick));
      });
  }

  function loadList() {
    const box = $("list-body");
    if (!box) return;
    box.textContent = "Cargando…";
    Promise.all([
      fetch("/api/projects", { credentials: "same-origin" }).then((r) => r.json()),
      fetch("/api/missions", { credentials: "same-origin" }).then((r) => r.json()),
    ]).then(([projects, missions]) => {
      if (!projects.length) {
        box.innerHTML = "<p>Aún no hay edificios. Usa Inicio o Ajustes para crear el primero.</p>";
        return;
      }
      box.innerHTML = projects
        .map((p) => {
          const ms = missions.filter((m) => m.project_id === p.id);
          const blocked = ms.filter((m) => m.blocked).length;
          return `<article class="mission-card" tabindex="0">
            <div class="kicker">${p.status_label || p.status}${p.is_demo ? " · DEMO" : ""}</div>
            <h3>${p.name}</h3>
            <p class="muted">Nv. ${p.level || 1} · ${p.missions || 0} misiones${blocked ? " · " + blocked + " bloqueadas" : ""} · meta ${p.goal_label || "sin definir"}</p>
            <ul>${ms
              .slice(0, 4)
              .map((m) => `<li>${m.blocked ? "⛔ " : ""}${m.title}${m.estimated_minutes == null ? " · sin estimar" : ""}</li>`)
              .join("")}</ul>
          </article>`;
        })
        .join("");
    });
  }

  function loadMoney() {
    fetch("/api/money", { credentials: "same-origin" })
      .then((r) => r.json())
      .then((data) => {
        const totals = $("money-totals");
        const list = $("money-list");
        const by = (data.totals && data.totals.currencies) || {};
        const keys = Object.keys(by);
        totals.innerHTML = (data.totals && data.totals.disclaimer ? `<p class="muted">${data.totals.disclaimer}</p>` : "") +
          (keys.length
            ? keys
                .map((cur) => {
                  const b = by[cur];
                  return `<p><b>${cur}</b> cobrado ${fmtMoney(b.received, cur)} · pagado ${fmtMoney(b.paid, cur)} · por cobrar ${fmtMoney(b.receivable, cur)} · por pagar ${fmtMoney(b.payable, cur)}</p>`;
                })
                .join("")
            : "<p class='muted'>Sin movimientos registrados.</p>");
        list.innerHTML = (data.items || [])
          .map(
            (m) =>
              `<div class="event-item">${m.direction === "in" ? "Ingreso" : "Gasto"} · ${m.status} · ${fmtMoney(m.amount_cents, m.currency)} · ${m.concept}
              ${m.status === "pending" ? `<button class="btn" type="button" data-partial="${m.id}" data-cents="${m.amount_cents}">Cobro parcial</button>` : ""}</div>`
          )
          .join("");
        list.querySelectorAll("[data-partial]").forEach((btn) => {
          btn.addEventListener("click", () => {
            const raw = window.prompt("Importe parcial (unidades, no centavos)", "0");
            if (!raw) return;
            post("/api/money/" + btn.dataset.partial + "/partial", { amount: raw }).then((res) => {
              if (res.error) toast(res.error);
              else loadMoney();
            });
          });
        });
      });
  }

  function loadWeek() {
    const box = $("week-body");
    if (!box) return;
    fetch("/api/week", { credentials: "same-origin" })
      .then((r) => r.json())
      .then((data) => {
        const g = (data.goals_done || []).map((x) => x.title).join(", ") || "ninguna";
        const blk = (data.blockers || []).map((x) => x.reason).join("; ") || "ninguno";
        box.innerHTML = `<p>Semana que empieza ${data.week_start}. Misiones terminadas: ${(data.missions_done || []).length}. Metas: ${g}.</p>
          <p>Minutos planificados: ${data.planned_minutes} · registrados: ${data.logged_minutes}.</p>
          <p>${(data.money && data.money.disclaimer) || ""}</p>
          <p>Bloqueos: ${blk}</p>
          <p>Oportunidades sin seguimiento: ${(data.stale_opportunities || []).length}</p>`;
      });
  }

  function search(q) {
    const box = $("search-hits");
    if (!box) return;
    if ((q || "").trim().length < 2) {
      box.innerHTML = "";
      return;
    }
    fetch("/api/search?q=" + encodeURIComponent(q), { credentials: "same-origin" })
      .then((r) => r.json())
      .then((hits) => {
        if (!hits.length) {
          box.innerHTML = "<p class='muted'>Sin resultados.</p>";
          return;
        }
        box.innerHTML = hits.map((h) => `<div class="event-item"><b>${h.type}</b> · ${h.title}</div>`).join("");
      });
  }

  function formData(form) {
    const out = {};
    new FormData(form).forEach((v, k) => {
      out[k] = v;
    });
    return out;
  }

  function bootOnboarding() {
    fetch("/api/world", { credentials: "same-origin" })
      .then((r) => r.json())
      .then((world) => {
        document.body.classList.toggle("quiet", (world.prefs || {}).gamification === "quiet");
        document.body.classList.toggle("no-anim", (world.prefs || {}).animations === false);
        if (world.needs_onboarding) {
          go("onboarding");
          const ov = $("overlay-onboarding");
          if (ov) ov.hidden = false;
        }
        const chip = $("stat-inbox");
        if (chip && world.inbox_open) {
          const b = chip.querySelector("b");
          if (b) b.textContent = String(Number(b.textContent || 0) + world.inbox_open);
        }
      });
  }

  $("btn-today")?.addEventListener("click", () => go("hoy"));
  $("btn-capture")?.addEventListener("click", () => go("captura"));

  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") {
      const open = overlays.some((n) => {
        const el = $("overlay-" + n);
        return el && !el.hidden;
      });
      if (open) {
        location.hash = "mapa";
      }
    }
    if (ev.ctrlKey && ev.shiftKey && (ev.key === "K" || ev.key === "k")) {
      ev.preventDefault();
      go("captura");
      $("capture-text")?.focus();
    }
  });

  $("today-budgets")?.querySelectorAll("[data-min]").forEach((btn) => {
    btn.addEventListener("click", () => {
      post("/api/today", { minutes: Number(btn.dataset.min) }).then(renderToday);
    });
  });
  $("today-accept")?.addEventListener("click", () => {
    post("/api/today", { accept: true }).then((data) => {
      renderToday(data);
      toast("Turno aceptado. Se conserva al recargar.");
    });
  });

  $("capture-save")?.addEventListener("click", () => {
    const text = $("capture-text")?.value || "";
    post("/api/inbox", { text }).then((row) => {
      if (row.error) {
        toast(row.error);
        return;
      }
      if ($("capture-text")) $("capture-text").value = "";
      loadInbox();
      toast("Guardado en la bandeja.");
    });
  });

  $("money-save")?.addEventListener("click", () => {
    const form = $("money-form");
    if (!form) return;
    post("/api/money", formData(form)).then((row) => {
      if (row.error) toast(row.error);
      else {
        form.reset();
        loadMoney();
      }
    });
  });

  $("onboard-empty")?.addEventListener("click", () => {
    const payload = formData($("onboard-form"));
    payload.path = "empty";
    post("/api/world/onboarding", payload).then(() => {
      toast("Mundo listo.");
      location.hash = "mapa";
      location.reload();
    });
  });
  $("onboard-demo")?.addEventListener("click", () => {
    const payload = formData($("onboard-form"));
    payload.path = "demo";
    post("/api/world/onboarding", payload).then(() => {
      toast("Demostración cargada. Está marcada como DEMO.");
      location.reload();
    });
  });
  $("onboard-skip")?.addEventListener("click", () => {
    post("/api/world/onboarding", { path: "skip", name: "Mi mundo" }).then(() => {
      location.hash = "mapa";
    });
  });

  $("week-save")?.addEventListener("click", () => {
    post("/api/week", {
      worked: $("week-worked")?.value,
      learned: $("week-learned")?.value,
      change: $("week-change")?.value,
    }).then(() => toast("Revisión guardada."));
  });

  $("search-q")?.addEventListener("input", (ev) => search(ev.target.value));

  const BOARD_NEXT = {
    idea: ["todo", "cancelled"],
    todo: ["planned", "active", "waiting", "cancelled"],
    planned: ["active", "todo", "cancelled"],
    active: ["waiting", "review", "done", "todo"],
    waiting: ["active", "todo"],
    review: ["done", "active"],
    done: ["todo", "archived"],
    cancelled: ["todo"],
  };

  function loadBoard() {
    const grid = $("board-grid");
    if (!grid) return;
    grid.textContent = "Cargando…";
    fetch("/api/board", { credentials: "same-origin" })
      .then((r) => r.json())
      .then((data) => {
        const wip = data.wip || {};
        if ($("board-wip")) {
          $("board-wip").textContent =
            "Puestos activos " + (wip.used || 0) + " / " + (wip.limit || 3) +
            ". El número de personajes no aumenta las horas. Arrastra o usa el teclado.";
        }
        const watch = $("board-watch");
        if (watch) {
          watch.innerHTML = (data.watch || [])
            .slice(0, 4)
            .map((a) => `<div class="event-item"><b>${esc(a.rule)}</b> · ${esc(a.title)}<div class="muted">${esc(a.action || "")}</div></div>`)
            .join("");
        }
        const labels = data.labels || {};
        const columns = data.columns || {};
        const order = ["idea", "todo", "planned", "active", "waiting", "review", "done"];
        grid.innerHTML = order
          .map((key) => {
            const cards = columns[key] || [];
            return `<div class="board-col" data-col="${key}">
              <h3>${labels[key] || key} <span>${cards.length}</span></h3>
              ${cards
                .map(
                  (m) => `<article class="board-card" draggable="true" tabindex="0" data-id="${m.id}" data-version="${m.version || 1}" data-state="${m.work_state}">
                    <div class="kicker">${esc(m.project_name || "")} · ${esc(m.specialty || "")}</div>
                    <h4>${esc(m.title)}</h4>
                    <p class="muted">${esc(m.next_action || (m.estimated_minutes == null ? "sin estimar" : m.estimated_minutes + " min"))}${m.blocked ? " · bloqueada" : ""}</p>
                    <div class="row-actions">
                      ${(BOARD_NEXT[key] || []).map((st) => `<button class="btn" type="button" data-move="${st}">${st}</button>`).join("")}
                    </div>
                  </article>`
                )
                .join("")}
            </div>`;
          })
          .join("");
        grid.querySelectorAll(".board-card").forEach((card) => bindCard(card));
        const queues = $("board-queues");
        if (queues) {
          queues.innerHTML = (data.queue || [])
            .map(
              (q) =>
                `<article class="mission-card"><div class="kicker">Cola · ${esc(q.name)}</div><ol>${(q.items || [])
                  .map((i) => `<li>${i.blocked ? "⛔ " : ""}${esc(i.title)} · ${esc(i.work_state)}${i.estimated_minutes == null ? " · sin estimar" : ""}</li>`)
                  .join("")}</ol></article>`
            )
            .join("");
        }
      })
      .catch(() => {
        grid.textContent = "No se pudo cargar el tablero.";
      });
  }

  function bindCard(card) {
    card.addEventListener("dragstart", (ev) => {
      ev.dataTransfer.setData("text/plain", card.dataset.id);
      ev.dataTransfer.setData("version", card.dataset.version);
    });
    card.querySelectorAll("[data-move]").forEach((btn) => {
      btn.addEventListener("click", () => moveCard(card.dataset.id, btn.dataset.move, card.dataset.version));
    });
    card.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") {
        fetch("/api/missions")
          .then((r) => r.json())
          .then((items) => {
            const m = (items || []).find((x) => String(x.id) === String(card.dataset.id));
            if (m && window.DRWorld && window.DRWorld.openBuilding) {
              /* keep keyboard path */
            }
            location.hash = "misiones";
          });
      }
    });
  }

  $("board-grid")?.addEventListener("dragover", (ev) => {
    const col = ev.target.closest(".board-col");
    if (!col) return;
    ev.preventDefault();
  });
  $("board-grid")?.addEventListener("drop", (ev) => {
    const col = ev.target.closest(".board-col");
    if (!col) return;
    ev.preventDefault();
    const id = ev.dataTransfer.getData("text/plain");
    const version = ev.dataTransfer.getData("version");
    moveCard(id, col.dataset.col, version);
  });

  function moveCard(id, state, version) {
    const extra = {};
    if (state === "waiting") {
      extra.wait_reason = window.prompt("Motivo de la espera", "Pendiente externo") || "";
      if (!extra.wait_reason) return;
      extra.wait_review_on = window.prompt("Fecha de seguimiento (YYYY-MM-DD)", "") || undefined;
    }
    post("/api/board/missions/" + id + "/move", { work_state: state, version: Number(version) || undefined, ...extra }).then((res) => {
      if (res.error) {
        toast(res.error);
        loadBoard();
        return;
      }
      toast("Orden actualizada.");
      loadBoard();
      if (window.DRMap && window.DRMap.refresh) window.DRMap.refresh();
    });
  }

  function loadJournal() {
    fetch("/api/journal", { credentials: "same-origin" })
      .then((r) => r.json())
      .then((rows) => {
        const box = $("journal-list");
        if (!box) return;
        box.innerHTML = (rows || [])
          .map((j) => `<article class="mission-card"><div class="kicker">${esc(j.status)}</div><p>${esc(j.text)}</p></article>`)
          .join("") || "<p class='muted'>Sin entradas.</p>";
      });
  }

  function renderProposal(entry) {
    const box = $("journal-proposal");
    if (!box) return;
    const proposal = entry.proposal || {};
    const actions = proposal.actions || [];
    box.innerHTML =
      `<p>Fecha interpretada: ${proposal.effective_date || "hoy"}${proposal.date_expression ? " (" + proposal.date_expression + ")" : ""}. Origen: reglas locales.</p>` +
      actions
        .map(
          (a) => `<article class="mission-card">
            <div class="kicker">${a.type} · ${a.status}</div>
            <h3>${esc(a.label || a.type)}</h3>
            <p>${esc(a.text)}</p>
            ${(a.missing || []).map((m) => `<p class="muted">${esc(m)}</p>`).join("")}
            <label><input type="checkbox" data-aid="${a.id}" ${a.status === "ready" ? "checked" : ""}> Aplicar esta acción</label>
          </article>`
        )
        .join("") +
      `<button class="btn solid" type="button" id="journal-apply">Aplicar seleccionadas</button>`;
    $("journal-apply")?.addEventListener("click", () => {
      const accepted = [...box.querySelectorAll("input[data-aid]:checked")].map((i) => i.dataset.aid);
      post("/api/journal/" + entry.id + "/apply", { accepted }).then((row) => {
        if (row.error) {
          toast(row.error);
          return;
        }
        toast("Cambios aplicados según lo aceptado.");
        renderProposal(row);
        loadJournal();
        loadBoard();
        if (window.DRMap && window.DRMap.refresh) window.DRMap.refresh();
      });
    });
  }

  $("journal-save")?.addEventListener("click", () => {
    const text = $("journal-text")?.value || "";
    post("/api/journal", { text }).then((row) => {
      if (row.error) {
        toast(row.error);
        return;
      }
      if ($("journal-text")) $("journal-text").value = "";
      renderProposal(row);
      loadJournal();
      toast("Borrador guardado. Nada se aplicó todavía.");
    });
  });

  window.DRWorldUI = {
    onOpen(name) {
      if (name === "hoy") loadToday();
      if (name === "captura") {
        loadInbox();
        $("capture-text")?.focus();
      }
      if (name === "lista") loadList();
      if (name === "finanzas") loadMoney();
      if (name === "revision") loadWeek();
      if (name === "tablero") loadBoard();
      if (name === "bitacora") loadJournal();
      if (name === "onboarding") $("onboard-form")?.querySelector("input")?.focus();
    },
  };

  if (document.querySelector(".world-map")) bootOnboarding();
})();
