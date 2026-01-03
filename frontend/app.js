const qs = (s) => document.querySelector(s)

const state = {
  route: "catalog",
  apiBase: localStorage.getItem("apiBase") || "http://localhost:8002",
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

function renderDetails(m) {
  const host = qs("#movieDetails")

  if (!m) {
    host.innerHTML = `<div class="empty">Выбери фильм из списка слева.</div>`
    return
  }

  const desc = (m.override?.description ?? m.description ?? "").trim() || "— нет описания —"
  const videoUrl = m.video?.url ? `${state.apiBase}${m.video.url}` : `${state.apiBase}/stream/${m.movie_id}.mp4`

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

    <div class="muted">Видео</div>
    <div style="margin-top:8px;">
      <video id="player" controls preload="metadata" style="width:100%; border-radius:14px; background:#000;">
        <source src="${videoUrl}" type="video/mp4" />
      </video>
      <div class="muted" style="margin-top:8px; font-size:12px;">
        Если видео 404 — положи файл <b>${m.movie_id}.mp4</b> в папку <b>./videos</b> на хосте и пробрось её в backend.
      </div>
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

function renderList() {
  const list = qs("#list")
  list.innerHTML = ""

  if (!state.items.length) {
    list.innerHTML = `<div class="empty">Ничего не найдено.</div>`
    qs("#countLabel").textContent = `0`
    return
  }

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
    renderDetails(data)
  } catch (e) {
    toast("bad", "Failed to fetch", String(e))
  }
}

async function loadMovies() {
  const q = qs("#q").value.trim()

  const params = new URLSearchParams()
  if (q) params.set("q", q)
  params.set("limit", String(state.limit))
  params.set("offset", String(state.offset))

  try {
    const r = await safeFetch(`/movies?${params.toString()}`)
    if (!r.ok) {
      const t = await r.text()
      toast("bad", "Не удалось загрузить фильмы", `${r.status}: ${t.slice(0, 200)}`)
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
    if (state.selected?.movie_id === movieId) openMovie(movieId)
  } catch (e) {
    toast("bad", "Failed to fetch", String(e))
  }
}

async function obsGet(path) {
  try {
    const r = await safeFetch(path, { headers: { "Content-Type": "text/plain" } })
    const text = await r.text()
    qs("#obsOut").textContent = `GET ${path}\n\n${text}`
  } catch (e) {
    qs("#obsOut").textContent = `GET ${path}\n\n${String(e)}`
  }
}

function logEvent(type, movieId, extra = {}) {
  const out = qs("#activityOut")
  if (!out) return
  const line = `${new Date().toLocaleTimeString()} • ${type} • movie_id=${movieId}${extra.t != null ? ` • t=${extra.t}s` : ""}`
  out.textContent = (out.textContent === "—" ? line : `${line}\n${out.textContent}`)
}

function init() {
  document.querySelectorAll(".navItem").forEach(b => b.onclick = () => setRoute(b.dataset.route))

  const refreshBtn = qs("#refresh")
  if (refreshBtn) refreshBtn.onclick = () => { state.offset = 0; loadMovies() }

  qs("#prev").onclick = () => { state.offset = Math.max(0, state.offset - state.limit); loadMovies() }
  qs("#next").onclick = () => { state.offset = state.offset + state.limit; loadMovies() }

  qs("#q").addEventListener("input", () => {
    clearTimeout(state.debounce)
    state.debounce = setTimeout(() => { state.offset = 0; loadMovies() }, 250)
  })

  qs("#ovLoad").onclick = loadOverride
  qs("#ovSave").onclick = saveOverride

  qs("#btnPing").onclick = () => obsGet("/ping")
  qs("#btnHealth").onclick = () => obsGet("/health")
  qs("#btnMetrics").onclick = () => obsGet("/metrics")

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

  loadMovies()
}

init()
