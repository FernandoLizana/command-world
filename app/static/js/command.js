document.querySelectorAll(".flash").forEach((el) => {
  setTimeout(() => {
    el.style.opacity = "0";
    el.style.transition = "opacity .4s";
  }, 4200);
});

(function () {
  const gear = document.getElementById("rail-gear");
  const menu = document.getElementById("rail-menu");
  if (gear && menu) {
    gear.addEventListener("click", (ev) => {
      ev.stopPropagation();
      menu.hidden = !menu.hidden;
    });
    document.addEventListener("click", () => {
      menu.hidden = true;
    });
    menu.addEventListener("click", (ev) => ev.stopPropagation());
  }
  const mapUrl = document.querySelector(".world-map") ? null : "/";
  document.getElementById("btn-today")?.addEventListener("click", () => {
    window.location.href = mapUrl ? mapUrl + "#hoy" : "#hoy";
  });
  document.getElementById("btn-capture")?.addEventListener("click", () => {
    window.location.href = mapUrl ? mapUrl + "#captura" : "#captura";
  });
})();

(function () {
  const world = document.querySelector(".world-map");
  if (!world) return;

  const state = {
    selected: null,
    brief: null,
    advice: null,
  };

  function $(id) {
    return document.getElementById(id);
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
    const wrap = document.querySelector(".flash-wrap") || document.createElement("div");
    if (!wrap.classList.contains("flash-wrap")) {
      wrap.className = "flash-wrap";
      document.querySelector(".stage")?.appendChild(wrap);
    }
    const el = document.createElement("div");
    el.className = "flash";
    el.textContent = msg;
    wrap.appendChild(el);
    setTimeout(() => {
      el.style.opacity = "0";
      el.style.transition = "opacity .4s";
      setTimeout(() => el.remove(), 500);
    }, 3200);
  }

  function closeOverlays() {
    document.querySelectorAll(".overlay").forEach((el) => {
      el.hidden = true;
    });
    document.querySelectorAll(".rail a").forEach((a) => a.classList.remove("on"));
  }

  function openOverlay(name) {
    closeOverlays();
    if (!name || name === "mapa") {
      history.replaceState(null, "", location.pathname);
      markNav("mapa");
      return;
    }
    const el = $("overlay-" + name);
    if (!el) return;
    el.hidden = false;
    markNav(name);
    if (name === "misiones") loadMissions();
    if (name === "ia") ask("¿Qué hago ahora?");
    if (name === "historial") loadHistory();
    if (window.DRWorldUI && window.DRWorldUI.onOpen) window.DRWorldUI.onOpen(name);
    const focusable = el.querySelector("input, textarea, button, [tabindex]");
    if (focusable) focusable.focus();
  }

  function markNav(name) {
    document.querySelectorAll(".rail a[data-overlay]").forEach((a) => {
      a.classList.toggle("active", a.dataset.overlay === name);
    });
  }

  function hashName() {
    return (location.hash || "#mapa").replace("#", "") || "mapa";
  }

  window.addEventListener("hashchange", () => openOverlay(hashName()));

  document.querySelectorAll("[data-close-overlay]").forEach((btn) => {
    btn.addEventListener("click", () => {
      closeOverlays();
      location.hash = "mapa";
    });
  });

  $("cp-close")?.addEventListener("click", () => {
    const panel = $("city-panel");
    if (panel) panel.hidden = true;
  });

  function statusLabel(city) {
    return city.status_label || city.status || "—";
  }

  function fillPanel(city) {
    state.selected = city;
    const panel = $("city-panel");
    if (!panel) return;
    panel.hidden = false;
    $("cp-name").textContent = city.name;
    $("cp-status").textContent = city.kind === "advisor" ? "Centro de mando" : "Territorio";
    $("cp-status-val").textContent = statusLabel(city);
    const progress = Math.max(0, Math.min(100, Number(city.progress) || 0));
    $("cp-progress").textContent = progress + "%";
    $("cp-progress-bar").style.width = progress + "%";
    $("cp-health").textContent = (city.health || 0) + "%";
    $("cp-health-bar").style.width = (city.health || 0) + "%";
    $("cp-priority").textContent = city.priority != null ? "P" + city.priority : "—";
    const details = $("cp-details");
    details.hidden = true;
    details.innerHTML = city.description
      ? `<p>${city.description}</p><p class="muted">Nv. ${city.level || 1} · ${city.missions || 0} misiones · ${city.alerts || 0} alertas · meta ${city.goal_label || "sin definir"} · fase ${city.construction && city.construction.label ? city.construction.label : "sin definir"}${city.blocked ? " · hay bloqueos" : ""}</p>`
      : `<p class="muted">Nv. ${city.level || 1} · ${city.missions || 0} misiones · ${city.alerts || 0} alertas · meta ${city.goal_label || "sin definir"} · fase ${city.construction && city.construction.label ? city.construction.label : "sin definir"}${city.blocked ? " · hay bloqueos" : ""}</p>`;
  }

  function showAdvisor() {
    fillPanel({
      id: "command",
      kind: "advisor",
      name: "Centro de Mando IA",
      status_label: "Asesor",
      progress: 100,
      health: 100,
      priority: 0,
      description: "Pregunta qué hacer ahora. La IA recomienda. Tú decides.",
    });
    location.hash = "ia";
  }

  function continueMission(id) {
    if (!id) {
      toast("No hay una misión lista. Pregunta al Centro de Mando IA.");
      return Promise.resolve();
    }
    return post(`/api/missions/${id}/continue`).then((data) => {
      if (data.error) {
        toast("No se pudo continuar la misión.");
        return data;
      }
      const xp = data.xp ? ` +${data.xp} XP` : "";
      toast((data.completed_mission ? "Misión cumplida." : "Objetivo listo.") + xp);
      if (window.DRMap && window.DRMap.refresh) window.DRMap.refresh();
      if (!$("overlay-misiones").hidden) loadMissions();
      if (!$("overlay-mission-brief").hidden && data.mission) renderBrief(data.mission);
      return data;
    });
  }

  function nextMission(projectId) {
    const url = projectId ? `/api/missions?project_id=${projectId}` : "/api/missions";
    return fetch(url, { credentials: "same-origin" })
      .then((r) => r.json())
      .then((items) => (items && items[0]) || null);
  }

  $("cp-continue")?.addEventListener("click", () => {
    const city = state.selected;
    if (!city) return;
    if (city.kind === "advisor") {
      location.hash = "ia";
      return;
    }
    nextMission(city.id).then((m) => {
      if (!m) {
        toast("Sin misiones en este territorio.");
        return;
      }
      continueMission(m.id);
    });
  });

  $("cp-mission")?.addEventListener("click", () => {
    const city = state.selected;
    if (!city || city.kind === "advisor") {
      location.hash = "misiones";
      return;
    }
    nextMission(city.id).then((m) => {
      if (!m) {
        location.hash = "misiones";
        return;
      }
      renderBrief(m);
    });
  });

  $("cp-talk")?.addEventListener("click", () => {
    const city = state.selected;
    const q = city && city.kind !== "advisor"
      ? `¿Qué debería hacer ahora en ${city.name}?`
      : "¿Qué hago ahora?";
    location.hash = "ia";
    ask(q);
  });

  $("cp-detail")?.addEventListener("click", () => {
    const details = $("cp-details");
    if (details) details.hidden = !details.hidden;
  });

    function renderBrief(mission) {
    state.brief = mission;
    const ia = $("overlay-ia");
    if (ia) ia.hidden = true;
    $("overlay-mission-brief").hidden = false;
    $("brief-title").textContent = mission.title;
    $("brief-project").textContent = mission.project_name || "";
    const objs = $("brief-objectives");
    objs.innerHTML = "";
    (mission.objectives || []).forEach((o) => {
      const li = document.createElement("li");
      li.textContent = (o.completed ? "☑ " : "☐ ") + o.description;
      if (o.completed) li.classList.add("done");
      objs.appendChild(li);
    });
    if (!(mission.objectives || []).length) {
      objs.innerHTML = "<li>Sin objetivos desglosados. Continuar completa la misión.</li>";
    }
    $("brief-reward").textContent = `Recompensa: + progreso · +${mission.xp_reward || 5} XP`;
  }

  $("brief-continue")?.addEventListener("click", () => {
    if (state.brief) continueMission(state.brief.id);
  });

  function missionCard(m) {
    const wrap = document.createElement("article");
    wrap.className = "mission-card";
    const done = (m.objectives || []).filter((o) => o.completed).length;
    const total = (m.objectives || []).length;
    wrap.innerHTML = `
      <div class="kicker">${m.project_name || ""} · P${m.priority || 3}</div>
      <h3>${m.title}</h3>
      <div class="track green"><i style="width:${m.progress || 0}%"></i></div>
      <p class="muted">${done}/${total || 1} objetivos · +${m.xp_reward || 5} XP</p>
      <div class="row-actions">
        <button class="btn solid" type="button" data-go="${m.id}">Continuar</button>
        <button class="btn" type="button" data-brief="${m.id}">Ver</button>
      </div>`;
    wrap.querySelector("[data-go]")?.addEventListener("click", () => continueMission(m.id));
    wrap.querySelector("[data-brief]")?.addEventListener("click", () => renderBrief(m));
    return wrap;
  }

  function loadMissions(projectId) {
    const box = $("missions-list");
    box.textContent = "Cargando…";
    const url = projectId ? `/api/missions?project_id=${projectId}` : "/api/missions";
    fetch(url, { credentials: "same-origin" })
      .then((r) => r.json())
      .then((items) => {
        box.innerHTML = "";
        if (!items.length) {
          box.innerHTML = "<p class='muted'>No hay misiones abiertas. Pregunta al Centro de Mando IA.</p>";
          return;
        }
        items.forEach((m) => box.appendChild(missionCard(m)));
      })
      .catch(() => {
        box.textContent = "No se pudieron cargar las misiones.";
      });
  }

  function loadHistory() {
    const box = $("history-list");
    box.textContent = "Cargando…";
    fetch("/api/events?limit=40", { credentials: "same-origin" })
      .then((r) => r.json())
      .then((items) => {
        box.innerHTML = "";
        if (!items.length) {
          box.innerHTML = "<p class='muted'>Aún no hay crónica.</p>";
          return;
        }
        items.forEach((e) => {
          const row = document.createElement("div");
          row.className = "event-item";
          row.innerHTML = `<b>${e.project_name || "Imperio"}</b> · ${e.title}<div class="when">${e.created_at || ""}</div>`;
          box.appendChild(row);
        });
      })
      .catch(() => {
        box.textContent = "No se pudo cargar el historial.";
      });
  }

  function ask(question) {
    const box = $("ia-answer");
    box.textContent = "Pensando…";
    post("/api/advisor/brief", { question }).then((data) => {
      state.advice = data;
      box.textContent = (data.answer || data.summary || "Sin consejo.") + (
        data.ai_status === "rules" ? " (Reglas locales.)" : " (Modelo opcional.)"
      );
      const create = $("ia-create");
      if (data.create_mission && data.create_mission.project_id) {
        create.hidden = false;
        create.dataset.title = data.create_mission.title || "";
        create.dataset.project = String(data.create_mission.project_id);
      } else {
        create.hidden = true;
      }
      const now = $("now-text");
      if (now && data.priority_project) {
        now.textContent = data.priority_project + (data.suggested_mission ? " · " + data.suggested_mission.title : "");
      }
    }).catch(() => {
      box.textContent = "El asesor no respondió.";
    });
  }

  document.querySelectorAll("[data-ask]").forEach((btn) => {
    btn.addEventListener("click", () => ask(btn.dataset.ask));
  });

  $("ia-create")?.addEventListener("click", () => {
    const btn = $("ia-create");
    post("/api/missions/from-advice", {
      project_id: Number(btn.dataset.project),
      title: btn.dataset.title,
    }).then((data) => {
      if (!data.ok) {
        toast("No se pudo crear la misión.");
        return;
      }
      toast(data.created ? "Misión desplegada." : "Esa misión ya estaba abierta.");
      if (data.mission) renderBrief(data.mission);
      if (window.DRMap && window.DRMap.refresh) window.DRMap.refresh();
    });
  });

  window.DRWorld = {
    openBuilding(city) {
      if (!city) return;
      if (city.kind === "advisor") {
        showAdvisor();
        return;
      }
      fillPanel(city);
    },
    openMission(id) {
      fetch("/api/missions", { credentials: "same-origin" })
        .then((r) => r.json())
        .then((items) => {
          const m = (items || []).find((x) => String(x.id) === String(id));
          if (m) renderBrief(m);
          else location.hash = "tablero";
        });
    },
    setNow(text) {
      const el = $("now-text");
      if (el && text) el.textContent = text;
    },
    toast,
  };

  openOverlay(hashName());
})();
