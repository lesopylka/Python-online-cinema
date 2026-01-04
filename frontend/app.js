const qs = (s) => document.querySelector(s)

const state = {
  route: "catalog",
  apiBase: localStorage.getItem("apiBase") || "http://localhost:8000",

  entity: "movies",

  items: [],
  total: 0,
  limit: 12,
  offset: 0,

  selected: null,
  debounce: null,
}

function toast(type, title, msg) {
  const host = qs("#toastHost")
  const el = document.createElement("div")
  el.className = `toast ${type}`
  el.innerHTML = `<div class="toastTitle">${title}</div><div class="toastMsg">${msg}</div>`
  host.appendChild(el)
  setTimeout(() => el.remove(), 3800)
}

function setRoute(route) {
  state.route = route
  qs("#pageTitle").textContent =
    route === "catalog" ? "Каталог" :
    route === "override" ? "Override" :
    route === "analytics" ? "Аналитика" : "Наблюдаемость"

  document.querySelectorAll(".navItem").forEach(b => b.classList.toggle("isActive", b.dataset.route === route))
  document.querySelectorAll(".page").forEach(p => p.classList.add("isHidden"))
  qs(`#page-${route}`).classList.remove("isHidden")

  if (route === "obs") loadLogs()
}

function apiUrl(path) {
  return `${state.apiBase}${path}`
}

async function safeFetch(path, opts = {}) {
  return fetch(apiUrl(path), {
    ...opts,
    headers: {
      ...(opts.headers || {}),
    },
  })
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;")
}

function setDetailsEmpty() {
  qs("#detailsTitle").textContent = "Карточка"
  qs("#detailsHost").innerHTML = `<div class="empty">Выберите фильм или актёра из списка ниже.</div>`
}

function renderMovieDetails(m) {
  const host = qs("#detailsHost")
  qs("#detailsTitle").textContent = "Фильм"

  if (!m) {
    host.innerHTML = `<div class="empty">Выберите фильм из списка ниже.</div>`
    return
  }

  const desc = (m.override?.description ?? m.description ?? "").trim() || "— нет описания —"
  const videoUrl = m.video?.url ? `${state.apiBase}${m.video.url}` : `${state.apiBase}/stream/${m.movie_id}.mp4`

  const actors = Array.isArray(m.actors) ? m.actors : []

  host.innerHTML = `
    <div style="font-weight:900;font-size:18px;">${escapeHtml(m.title || "Без названия")}</div>

    <div style="height:10px"></div>

    <div class="movieMeta">
      <span class="badge">id: ${m.movie_id}</span>
      <span class="badge">${escapeHtml(m.language || "—")}</span>
      <span class="badge ${m.source_used === "cms" ? "ok" : "warn"}">${escapeHtml(m.source_used || "—")}</span>
    </div>

    <div style="height:12px"></div>

    <div class="muted">Описание</div>
    <div style="white-space:pre-wrap;line-height:1.45;margin-top:6px;">${escapeHtml(desc)}</div>

    <div style="height:14px"></div>

    <div class="muted">Актёры</div>
    <div style="margin-top:8px; display:grid; gap:8px;">
      ${actors.length ? actors.map(a => `
        <div class="movieCard" data-actor-id="${a.actor_id}">
          <div class="movieTitle">${escapeHtml(a.full_name || "Без имени")}</div>
          <div class="movieMeta">
            <span class="badge">id: ${a.actor_id}</span>
            <span class="badge">${escapeHtml(a.role_name || "—")}</span>
            <span class="badge">${escapeHtml(a.birth_date || "—")}</span>
          </div>
        </div>
      `).join("") : `<div class="empty">Нет актёров для этого фильма.</div>`}
    </div>

    <div class="divider"></div>

    <div class="muted">Видео</div>
    <div style="margin-top:8px;" class="playerWrap">
      <video id="player" class="player" controls preload="metadata">
        <source src="${videoUrl}" type="video/mp4" />
      </video>
    </div>

    <div class="muted" style="margin-top:8px; font-size:12px;">
      Если видео 404 — положи файл <b>${m.movie_id}.mp4</b> в папку <b>./videos</b> на хосте и пробрось её в backend.
    </div>

    <div style="height:14px"></div>

    <div class="row">
      <button class="btn btnGhost" id="copyMovieId">Скопировать id</button>
      <button class="btn btnPrimary" id="toOverride">Override</button>
    </div>
  `

  qs("#copyMovieId").onclick = async () => {
    await navigator.clipboard.writeText(String(m.movie_id))
    toast("ok", "Скопировано", `movie_id = ${m.movie_id}`)
  }

  qs("#toOverride").onclick = () => {
    qs("#ovMovieId").value = String(m.movie_id)
    qs("#ovLang").value = (m.language || "ru")
    setRoute("override")
  }

  host.querySelectorAll("[data-actor-id]").forEach(el => {
    el.onclick = () => {
      const id = Number(el.getAttribute("data-actor-id"))
      if (!id) return
      openActor(id)
    }
  })

  const player = qs("#player")
  if (player) {
    player.addEventListener("play", () => logEvent("play", m.movie_id))
    player.addEventListener("pause", () => logEvent("pause", m.movie_id))
    player.addEventListener("ended", () => logEvent("stop", m.movie_id))

    let lastSent = 0
    player.addEventListener("timeupdate", () => {
      const now = Date.now()
      if (now - lastSent > 5000) {
        lastSent = now
        logEvent("progress", m.movie_id, { t: Math.floor(player.currentTime) })
      }
    })
  }
}

function renderActorDetails(a) {
  const host = qs("#detailsHost")
  qs("#detailsTitle").textContent = "Актёр"

  if (!a) {
    host.innerHTML = `<div class="empty">Выберите актёра из списка ниже.</div>`
    return
  }

  const movies = Array.isArray(a.movies) ? a.movies : []

  host.innerHTML = `
    <div style="font-weight:900;font-size:18px;">${escapeHtml(a.full_name || "Без имени")}</div>

    <div style="height:10px"></div>

    <div class="movieMeta">
      <span class="badge">id: ${a.actor_id}</span>
      <span class="badge">${escapeHtml(a.birth_date || "—")}</span>
    </div>

    <div style="height:14px"></div>

    <div class="row">
      <button class="btn btnGhost" id="copyActorId">Скопировать id</button>
      <button class="btn btnGhost" id="toActorsTab">Открыть в каталоге актёров</button>
    </div>

    <div class="divider"></div>

    <div class="muted">Фильмы</div>
    <div style="margin-top:8px; display:grid; gap:8px;">
      ${movies.length ? movies.map(m => `
        <div class="movieCard" data-movie-id="${m.movie_id}">
          <div class="movieTitle">${escapeHtml(m.title || "Без названия")}</div>
          <div class="movieMeta">
            <span class="badge">id: ${m.movie_id}</span>
            <span class="badge">${escapeHtml(m.role_name || "—")}</span>
          </div>
        </div>
      `).join("") : `<div class="empty">Нет фильмов для этого актёра.</div>`}
    </div>
  `

  qs("#copyActorId").onclick = async () => {
    await navigator.clipboard.writeText(String(a.actor_id))
    toast("ok", "Скопировано", `actor_id = ${a.actor_id}`)
  }

  qs("#toActorsTab").onclick = () => setEntity("actors")

  host.querySelectorAll("[data-movie-id]").forEach(el => {
    el.onclick = () => {
      const id = Number(el.getAttribute("data-movie-id"))
      if (!id) return
      setEntity("movies")
      openMovie(id)
    }
  })
}

function renderList() {
  const list = qs("#list")
  list.innerHTML = ""

  if (!state.items.length) {
    list.innerHTML = `<div class="empty">Ничего не найдено.</div>`
    qs("#countLabel").textContent = `0`
    return
  }

  if (state.entity === "movies") {
    for (const m of state.items) {
      const el = document.createElement("div")
      el.className = "movieCard"
      el.innerHTML = `
        <div class="movieTitle">${escapeHtml(m.title || "Без названия")}</div>
        <div class="movieMeta">
          <span class="badge">id: ${m.movie_id}</span>
          <span class="badge">${escapeHtml(m.language || "—")}</span>
          <span class="badge ${m.source_used === "cms" ? "ok" : "warn"}">${escapeHtml(m.source_used || "—")}</span>
        </div>
      `
      el.onclick = () => openMovie(m.movie_id)
      list.appendChild(el)
    }
  } else {
    for (const a of state.items) {
      const el = document.createElement("div")
      el.className = "movieCard"
      el.innerHTML = `
        <div class="movieTitle">${escapeHtml(a.full_name || "Без имени")}</div>
        <div class="movieMeta">
          <span class="badge">id: ${a.actor_id}</span>
          <span class="badge">${escapeHtml(a.birth_date || "—")}</span>
        </div>
      `
      el.onclick = () => openActor(a.actor_id)
      list.appendChild(el)
    }
  }

  const start = state.total ? (state.offset + 1) : (state.offset + 1)
  const end = state.offset + state.items.length
  qs("#countLabel").textContent = state.total ? `${start}–${end} из ${state.total}` : `${start}–${end}`
}

async function openMovie(movieId) {
  try {
    const r = await safeFetch(`/movies/${movieId}`)
    if (!r.ok) {
      const t = await r.text()
      toast("bad", "Ошибка /movies/{id}", `${r.status}: ${t.slice(0, 200)}`)
      return
    }
    const data = await r.json()
    state.selected = data
    renderMovieDetails(data)
  } catch (e) {
    toast("bad", "Failed to fetch", String(e))
  }
}

async function openActor(actorId) {
  try {
    const r = await safeFetch(`/actors/${actorId}`)
    if (!r.ok) {
      const t = await r.text()
      toast("bad", "Ошибка /actors/{id}", `${r.status}: ${t.slice(0, 200)}`)
      return
    }
    const data = await r.json()
    state.selected = data
    renderActorDetails(data)
  } catch (e) {
    toast("bad", "Failed to fetch", String(e))
  }
}

async function loadList() {
  const q = qs("#q").value.trim()

  const params = new URLSearchParams()
  if (q) params.set("q", q)
  params.set("limit", String(state.limit))
  params.set("offset", String(state.offset))

  const path = state.entity === "movies"
    ? `/movies?${params.toString()}`
    : `/actors?${params.toString()}`

  try {
    const r = await safeFetch(path)
    if (!r.ok) {
      const t = await r.text()
      toast("bad", "Не удалось загрузить список", `${r.status}: ${t.slice(0, 200)}`)
      state.items = []
      state.total = 0
      renderList()
      return
    }

    const data = await r.json()
    state.items = data.items || []
    state.total = data.total ?? 0
    renderList()
  } catch (e) {
    toast("bad", "Failed to fetch", String(e))
    state.items = []
    state.total = 0
    renderList()
  }
}

function setEntity(entity) {
  if (state.entity === entity) return

  state.entity = entity
  state.offset = 0
  state.items = []
  state.total = 0
  state.selected = null

  document.querySelectorAll(".tabBtn").forEach(b => b.classList.toggle("isActive", b.dataset.entity === entity))

  qs("#q").placeholder = entity === "movies" ? "Поиск по названию..." : "Поиск по имени..."
  setDetailsEmpty()
  loadList()
}

async function loadOverride() {
  const movieId = qs("#ovMovieId").value.trim()
  const lang = qs("#ovLang").value
  if (!movieId) return toast("warn", "Не хватает данных", "Укажи Movie ID")

  try {
    const r = await safeFetch(`/overrides/${movieId}?lang=${encodeURIComponent(lang)}`)
    if (r.ok) {
      const data = await r.json()
      qs("#ovText").value = data.description || ""
      qs("#ovMeta").textContent = `override найден, updated_at: ${data.updated_at}`
      toast("ok", "Загружено", "override подставлен в редактор")
    } else if (r.status === 404) {
      qs("#ovText").value = ""
      qs("#ovMeta").textContent = "override не найден (будет создан при сохранении)"
      toast("warn", "Нет override", "Это нормально — можно создать новый")
    } else {
      const t = await r.text()
      toast("bad", "Ошибка", `${r.status}: ${t.slice(0, 200)}`)
    }
  } catch (e) {
    toast("bad", "Failed to fetch", String(e))
  }
}

async function saveOverride() {
  const movieId = Number(qs("#ovMovieId").value.trim())
  const language = qs("#ovLang").value
  const description = qs("#ovText").value.trim()
  const editor_id = qs("#ovEditor").value.trim() || null

  if (!movieId || !description) return toast("warn", "Не хватает данных", "Нужен Movie ID и описание")

  try {
    const r = await safeFetch(`/overrides`, {
      method: "POST",
      body: JSON.stringify({ movie_id: movieId, language, description, editor_id }),
      headers: { "Content-Type": "application/json" },
    })
    if (!r.ok) {
      const t = await r.text()
      toast("bad", "Не сохранено", `${r.status}: ${t.slice(0, 200)}`)
      return
    }
    qs("#ovMeta").textContent = `сохранено, movie_id=${movieId}, lang=${language}`
    toast("ok", "Сохранено", "Override записан в базу")
    if (state.selected?.movie_id === movieId) openMovie(movieId)
  } catch (e) {
    toast("bad", "Failed to fetch", String(e))
  }
}

async function obsGet(path) {
  try {
    const r = await safeFetch(path)
    const ct = (r.headers.get("content-type") || "").toLowerCase()
    const text = await r.text()

    if (ct.includes("application/json")) {
      try {
        const obj = JSON.parse(text)
        qs("#obsOut").textContent = `GET ${path}\n\n` + JSON.stringify(obj, null, 2)
        return
      } catch (_) {
        qs("#obsOut").textContent = `GET ${path}\n\n${text}`
        return
      }
    }

    qs("#obsOut").textContent = `GET ${path}\n\n${text}`
  } catch (e) {
    qs("#obsOut").textContent = `GET ${path}\n\n${String(e)}`
  }
}


async function loadLogs() {
  const out = qs("#logsOut")
  if (!out) return

  try {
    const r = await safeFetch("/logs?limit=120")
    if (!r.ok) {
      const t = await r.text()
      out.textContent = `${r.status}\n${t.slice(0, 400)}`
      return
    }
    const data = await r.json()
    out.textContent = JSON.stringify(data.items || [], null, 2) || "—"
  } catch (e) {
    out.textContent = String(e)
  }
}

function logEvent(type, movieId, extra = {}) {
  const out = qs("#activityLog")
  if (!out) return
  const line = `${new Date().toLocaleTimeString()} • ${type} • movie_id=${movieId}${extra.t != null ? ` • t=${extra.t}s` : ""}`
  out.textContent = (out.textContent === "—" ? line : `${line}\n${out.textContent}`)
}

function init() {
  document.querySelectorAll(".navItem").forEach(b => b.onclick = () => setRoute(b.dataset.route))

  const refreshBtn = qs("#refresh")
  if (refreshBtn) refreshBtn.onclick = () => { state.offset = 0; loadList() }

  qs("#prev").onclick = () => { state.offset = Math.max(0, state.offset - state.limit); loadList() }
  qs("#next").onclick = () => { state.offset = state.offset + state.limit; loadList() }

  qs("#q").addEventListener("input", () => {
    clearTimeout(state.debounce)
    state.debounce = setTimeout(() => { state.offset = 0; loadList() }, 250)
  })

  document.querySelectorAll(".tabBtn").forEach(b => {
    b.onclick = () => setEntity(b.dataset.entity)
  })

  qs("#ovLoad").onclick = loadOverride
  qs("#ovSave").onclick = saveOverride

  qs("#btnPing").onclick = async () => { await obsGet("/ping"); loadLogs() }
  qs("#btnHealth").onclick = async () => { await obsGet("/health"); loadLogs() }
  qs("#btnMetrics").onclick = async () => { await obsGet("/metrics"); loadLogs() }
  qs("#btnLogs").onclick = async () => {
    await obsGet("/logs")
    await loadLogs()
  }


  qs("#runChecks").onclick = async () => {
    try {
      const r1 = await safeFetch("/ping")
      qs("#statPing").textContent = r1.ok ? "ok" : "fail"
    } catch (_) {
      qs("#statPing").textContent = "fail"
    }

    try {
      const r2 = await safeFetch("/metrics")
      qs("#statMetrics").textContent = r2.ok ? "ok" : "fail"
    } catch (_) {
      qs("#statMetrics").textContent = "fail"
    }

    qs("#statTracing").textContent = "см. Jaeger"
    toast("ok", "Проверка", "Готово")
  }

  setDetailsEmpty()
  loadList()
}

init()
