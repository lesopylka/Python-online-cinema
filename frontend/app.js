const qs = (s) => document.querySelector(s)

const state = {
  route: "catalog",
  apiBase: localStorage.getItem("apiBase") || "http://localhost:8002",

  tab: "movies",

  movies: [],
  moviesTotal: 0,
  moviesLimit: 12,
  moviesOffset: 0,

  actors: [],
  actorsTotal: 0,
  actorsLimit: 12,
  actorsOffset: 0,

  selectedType: null,
  selected: null,

  debounce: null,

  playerBoundFor: null,
  hbTimer: null,
  progressTimer: null,
}

function clearActivity() {
  const out = qs("#activityLog")
  if (out) out.textContent = "—"
}

function logEvent(type, movieId, extra = {}) {
  const out = qs("#activityLog")
  if (!out) return

  const line =
    `${new Date().toLocaleTimeString()} • ${type} • movie_id=${movieId}` +
    (extra.t != null ? ` • t=${extra.t}s` : "")

  out.textContent = (out.textContent === "—" ? line : `${line}\n${out.textContent}`)
}

function stopPlayerTimers() {
  if (state.hbTimer) { clearInterval(state.hbTimer); state.hbTimer = null }
  if (state.progressTimer) { clearInterval(state.progressTimer); state.progressTimer = null }
}

function bindPlayerEvents(movie) {
  stopPlayerTimers()

  const player = qs("#player")
  if (!player || !movie) return

  state.playerBoundFor = movie.movie_id

  player.addEventListener("play", () => {
    logEvent("play", movie.movie_id)

    if (!state.hbTimer) {
      state.hbTimer = setInterval(() => {
        logEvent("heartbeat", movie.movie_id, { t: Math.floor(player.currentTime || 0) })
      }, 15000)
    }

    if (!state.progressTimer) {
      state.progressTimer = setInterval(() => {
        logEvent("progress", movie.movie_id, { t: Math.floor(player.currentTime || 0) })
      }, 5000)
    }
  })

  player.addEventListener("pause", () => {
    logEvent("pause", movie.movie_id, { t: Math.floor(player.currentTime || 0) })
    stopPlayerTimers()
  })

  player.addEventListener("ended", () => {
    logEvent("stop", movie.movie_id, { t: Math.floor(player.currentTime || 0) })
    stopPlayerTimers()
  })

  player.addEventListener("error", () => {
    logEvent("error", movie.movie_id)
  })
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
}

function setTab(tab) {
  state.tab = tab
  document.querySelectorAll(".tabBtn").forEach(b => b.classList.toggle("isActive", b.dataset.tab === tab))
  qs("#tab-movies").classList.toggle("isHidden", tab !== "movies")
  qs("#tab-actors").classList.toggle("isHidden", tab !== "actors")

  stopPlayerTimers()
  clearActivity()

  state.selected = null
  state.selectedType = null

  renderDetails(null)
  renderVideo(null)
}

function apiUrl(path) {
  return `${state.apiBase}${path}`
}

async function safeFetch(path, opts = {}) {
  return fetch(apiUrl(path), {
    ...opts,
    headers: {
      "Content-Type": "application/json",
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

function renderVideo(movie) {
  const host = qs("#videoBlock")

  stopPlayerTimers()

  if (!movie) {
    host.innerHTML = `<div class="empty">Выберите фильм, чтобы загрузить видео.</div>`
    return
  }

  const videoUrl = movie.video?.url
    ? `${state.apiBase}${movie.video.url}`
    : `${state.apiBase}/stream/${movie.movie_id}.mp4`

  host.innerHTML = `
    <video id="player" controls preload="metadata"
      style="width:100%; max-width:520px; border-radius:14px; background:#000;">
      <source src="${videoUrl}" type="video/mp4" />
    </video>
    <div class="muted" style="margin-top:8px; font-size:12px;">
      Если видео 404 — положи файл <b>${movie.movie_id}.mp4</b> в папку <b>./videos</b>.
    </div>
  `
}

function renderDetails(payload) {
  const host = qs("#details")

  if (!payload) {
    host.innerHTML = `<div class="empty">Выбери фильм или актёра слева.</div>`
    return
  }

  if (payload.type === "actor") {
    const a = payload.actor
    host.innerHTML = `
      <div style="font-weight:900;font-size:18px;">${escapeHtml(a.full_name)}</div>
      <div style="height:10px"></div>
      <div class="movieMeta">
        <span class="badge">actor_id: ${a.actor_id}</span>
        <span class="badge">${a.birth_date ? escapeHtml(a.birth_date) : "— дата неизвестна —"}</span>
      </div>

      ${a.movies?.length ? `
        <div style="height:14px"></div>
        <div class="muted">Фильмы</div>
        <div style="margin-top:8px; display:grid; gap:8px;">
          ${a.movies.map(m => `
            <div class="badge" style="display:inline-flex; gap:8px; align-items:center;">
              <b>${escapeHtml(m.title)}</b>
              <span class="muted" style="font-size:12px;">id: ${m.movie_id}</span>
              ${m.role_name ? `<span class="muted" style="font-size:12px;">роль: ${escapeHtml(m.role_name)}</span>` : ""}
            </div>
          `).join("")}
        </div>
      ` : ""}
    `
    return
  }

  const m = payload.movie
  const actors = payload.actors || []
  const desc = (m.override?.description ?? m.description ?? "").trim() || "— нет описания —"

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
        <div class="badge" style="display:inline-flex; gap:8px; align-items:center; justify-content:space-between;">
          <span><b>${escapeHtml(a.full_name)}</b> <span class="muted" style="font-size:12px;">(id: ${a.actor_id})</span></span>
          <span class="muted" style="font-size:12px;">${a.role_name ? `роль: ${escapeHtml(a.role_name)}` : ""}</span>
        </div>
      `).join("") : `<div class="empty">У этого фильма нет актёров (или не загрузились).</div>`}
    </div>

    <div style="height:14px"></div>

    <div class="row">
      <button class="btn btnGhost" id="copyId">Скопировать id</button>
      <button class="btn btnPrimary" id="toOverride">Override</button>
    </div>
  `

  qs("#copyId").onclick = async () => {
    await navigator.clipboard.writeText(String(m.movie_id))
    toast("ok", "Скопировано", `movie_id = ${m.movie_id}`)
  }

  qs("#toOverride").onclick = () => {
    qs("#ovMovieId").value = String(m.movie_id)
    qs("#ovLang").value = (m.language || "ru")
    setRoute("override")
  }
}

function renderMoviesList() {
  const list = qs("#listMovies")
  list.innerHTML = ""

  if (!state.movies.length) {
    list.innerHTML = `<div class="empty">Ничего не найдено.</div>`
    qs("#countLabelMovies").textContent = `0`
    return
  }

  for (const m of state.movies) {
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

  const start = state.moviesOffset + 1
  const end = state.moviesOffset + state.movies.length
  qs("#countLabelMovies").textContent = state.moviesTotal ? `${start}–${end} из ${state.moviesTotal}` : `${start}–${end}`
}

function renderActorsList() {
  const list = qs("#listActors")
  list.innerHTML = ""

  if (!state.actors.length) {
    list.innerHTML = `<div class="empty">Ничего не найдено.</div>`
    qs("#countLabelActors").textContent = `0`
    return
  }

  for (const a of state.actors) {
    const el = document.createElement("div")
    el.className = "movieCard"
    el.innerHTML = `
      <div class="movieTitle">${escapeHtml(a.full_name || "Без имени")}</div>
      <div class="movieMeta">
        <span class="badge">id: ${a.actor_id}</span>
        <span class="badge">${a.birth_date ? escapeHtml(a.birth_date) : "—"}</span>
      </div>
    `
    el.onclick = () => openActor(a.actor_id)
    list.appendChild(el)
  }

  const start = state.actorsOffset + 1
  const end = state.actorsOffset + state.actors.length
  qs("#countLabelActors").textContent = state.actorsTotal ? `${start}–${end} из ${state.actorsTotal}` : `${start}–${end}`
}

async function openMovie(movieId) {
  try {
    clearActivity()
    stopPlayerTimers()

    const r = await safeFetch(`/movies/${movieId}`)
    if (!r.ok) {
      const t = await r.text()
      toast("bad", "Ошибка /movies/{id}", `${r.status}: ${t.slice(0, 200)}`)
      return
    }
    const movie = await r.json()

    const r2 = await safeFetch(`/movies/${movieId}/actors`)
    let actors = []
    if (r2.ok) {
      const data = await r2.json()
      actors = data.items || []
    }

    state.selectedType = "movie"
    state.selected = { movie, actors }

    renderDetails({ type: "movie", movie, actors })
    renderVideo(movie)

    bindPlayerEvents(movie)
  } catch (e) {
    toast("bad", "Failed to fetch", String(e))
  }
}

async function openActor(actorId) {
  try {
    clearActivity()
    stopPlayerTimers()

    const r = await safeFetch(`/actors/${actorId}`)
    if (!r.ok) {
      const t = await r.text()
      toast("bad", "Ошибка /actors/{id}", `${r.status}: ${t.slice(0, 200)}`)
      return
    }
    const actor = await r.json()

    state.selectedType = "actor"
    state.selected = actor

    renderDetails({ type: "actor", actor })
    renderVideo(null)
  } catch (e) {
    toast("bad", "Failed to fetch", String(e))
  }
}

async function loadMovies() {
  const q = qs("#q").value.trim()

  const params = new URLSearchParams()
  if (q) params.set("q", q)
  params.set("limit", String(state.moviesLimit))
  params.set("offset", String(state.moviesOffset))

  try {
    const r = await safeFetch(`/movies?${params.toString()}`)
    if (!r.ok) {
      const t = await r.text()
      toast("bad", "Не удалось загрузить фильмы", `${r.status}: ${t.slice(0, 200)}`)
      state.movies = []
      state.moviesTotal = 0
      renderMoviesList()
      return
    }

    const data = await r.json()
    state.movies = data.items || []
    state.moviesTotal = data.total ?? 0

    renderMoviesList()
  } catch (e) {
    toast("bad", "Failed to fetch", String(e))
    state.movies = []
    state.moviesTotal = 0
    renderMoviesList()
  }
}

async function loadActors() {
  const q = qs("#q").value.trim()

  const params = new URLSearchParams()
  if (q) params.set("q", q)
  params.set("limit", String(state.actorsLimit))
  params.set("offset", String(state.actorsOffset))

  try {
    const r = await safeFetch(`/actors?${params.toString()}`)
    if (!r.ok) {
      const t = await r.text()
      toast("bad", "Не удалось загрузить актёров", `${r.status}: ${t.slice(0, 200)}`)
      state.actors = []
      state.actorsTotal = 0
      renderActorsList()
      return
    }

    const data = await r.json()
    state.actors = data.items || []
    state.actorsTotal = data.total ?? 0

    renderActorsList()
  } catch (e) {
    toast("bad", "Failed to fetch", String(e))
    state.actors = []
    state.actorsTotal = 0
    renderActorsList()
  }
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
    })
    if (!r.ok) {
      const t = await r.text()
      toast("bad", "Не сохранено", `${r.status}: ${t.slice(0, 200)}`)
      return
    }
    qs("#ovMeta").textContent = `сохранено, movie_id=${movieId}, lang=${language}`
    toast("ok", "Сохранено", "Override записан в базу")
    if (state.selectedType === "movie" && state.selected?.movie?.movie_id === movieId) openMovie(movieId)
  } catch (e) {
    toast("bad", "Failed to fetch", String(e))
  }
}

async function obsGet(path) {
  try {
    const r = await safeFetch(path)
    const text = await r.text()
    try {
      const obj = JSON.parse(text)
      qs("#obsOut").textContent = `GET ${path}\n\n` + JSON.stringify(obj, null, 2)
    } catch (_) {
      qs("#obsOut").textContent = `GET ${path}\n\n${text}`
    }
  } catch (e) {
    qs("#obsOut").textContent = `GET ${path}\n\n${String(e)}`
  }
}

function init() {
  document.querySelectorAll(".navItem").forEach(b => b.onclick = () => setRoute(b.dataset.route))
  document.querySelectorAll(".tabBtn").forEach(b => b.onclick = () => setTab(b.dataset.tab))

  const refreshBtn = qs("#refresh")
  if (refreshBtn) refreshBtn.onclick = () => {
    if (state.tab === "movies") { state.moviesOffset = 0; loadMovies() }
    else { state.actorsOffset = 0; loadActors() }
  }

  qs("#prevMovies").onclick = () => { state.moviesOffset = Math.max(0, state.moviesOffset - state.moviesLimit); loadMovies() }
  qs("#nextMovies").onclick = () => { state.moviesOffset = state.moviesOffset + state.moviesLimit; loadMovies() }

  qs("#prevActors").onclick = () => { state.actorsOffset = Math.max(0, state.actorsOffset - state.actorsLimit); loadActors() }
  qs("#nextActors").onclick = () => { state.actorsOffset = state.actorsOffset + state.actorsLimit; loadActors() }

  qs("#q").addEventListener("input", () => {
    clearTimeout(state.debounce)
    state.debounce = setTimeout(() => {
      if (state.tab === "movies") { state.moviesOffset = 0; loadMovies() }
      else { state.actorsOffset = 0; loadActors() }
    }, 250)
  })

  qs("#ovLoad").onclick = loadOverride
  qs("#ovSave").onclick = saveOverride

  qs("#btnPing").onclick = () => obsGet("/ping")
  qs("#btnHealth").onclick = () => obsGet("/health")
  qs("#btnMetrics").onclick = () => obsGet("/metrics")
  qs("#btnLogs").onclick = () => obsGet("/logs?limit=200")

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

  setTab("movies")
  loadMovies()
  loadActors()
}

init()
