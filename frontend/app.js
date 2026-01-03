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
  if (!host) return
  const el = document.createElement("div")
  el.className = `toast ${type}`
  el.innerHTML = `<div class="toastTitle">${title}</div><div class="toastMsg">${msg}</div>`
  host.appendChild(el)
  setTimeout(() => el.remove(), 3800)
}

function setRoute(route) {
  state.route = route

  const titleEl = qs("#pageTitle")
  if (titleEl) {
    titleEl.textContent =
      route === "catalog" ? "Каталог" :
      route === "override" ? "Override" :
      route === "analytics" ? "Аналитика" : "Наблюдаемость"
  }

  document.querySelectorAll(".navItem").forEach(b =>
    b.classList.toggle("isActive", b.dataset.route === route)
  )

  document.querySelectorAll(".page").forEach(p => p.classList.add("isHidden"))
  const page = qs(`#page-${route}`)
  if (page) page.classList.remove("isHidden")
}

function apiUrl(path) {
  return `${state.apiBase}${path}`
}

async function safeFetch(path, opts = {}) {
  const r = await fetch(apiUrl(path), {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(opts.headers || {}),
    },
  })
  return r
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
  const box = qs("#movieDetails")
  if (!box) return

  if (!m) {
    box.innerHTML = `<div class="empty">Выбери фильм из списка ниже.</div>`
    return
  }

  const baseDesc = (m.description || "").trim() || "— нет описания —"
  const ov = m.override?.description ? m.override.description.trim() : ""
  const finalDesc = ov || baseDesc

  box.innerHTML = `
    <div class="muted">movie_id</div>
    <div style="font-weight:900;font-size:18px;margin-top:4px;">${m.movie_id}</div>

    <div style="height:10px"></div>

    <div style="font-weight:900;font-size:16px;">${escapeHtml(m.title || "Без названия")}</div>

    <div style="height:10px"></div>

    <div class="movieMeta">
      <span class="badge">${escapeHtml(m.language || "—")}</span>
      <span class="badge ${m.source_used === "cms" ? "ok" : "warn"}">${escapeHtml(m.source_used || "—")}</span>
      <span class="badge">${escapeHtml(m.updated_at ? new Date(m.updated_at).toLocaleString() : "—")}</span>
    </div>

    <div style="height:12px"></div>

    <div class="muted">Описание ${ov ? `<span class="badge ok">override</span>` : ""}</div>
    <div style="white-space:pre-wrap;line-height:1.45;margin-top:6px;">${escapeHtml(finalDesc)}</div>

    <div style="height:14px"></div>

    <div class="row">
      <button class="btn btnGhost" id="copyId">Скопировать movie_id</button>
      <button class="btn btnPrimary" id="toOverride">Редактировать override</button>
    </div>
  `

  const copyBtn = qs("#copyId")
  if (copyBtn) {
    copyBtn.onclick = async () => {
      await navigator.clipboard.writeText(String(m.movie_id))
      toast("ok", "Скопировано", `movie_id = ${m.movie_id}`)
    }
  }

  const toOvBtn = qs("#toOverride")
  if (toOvBtn) {
    toOvBtn.onclick = () => {
      const idEl = qs("#ovMovieId")
      const langEl = qs("#ovLang")
      if (idEl) idEl.value = String(m.movie_id)
      if (langEl) langEl.value = m.language || "ru"
      setRoute("override")
    }
  }
}

function renderList() {
  const list = qs("#list")
  const count = qs("#countLabel")
  if (!list) return

  list.innerHTML = ""

  if (!state.items.length) {
    list.innerHTML = `<div class="empty">Ничего не найдено. Попробуй другой запрос.</div>`
    if (count) count.textContent = `0`
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

  if (count) {
    const from = state.offset + 1
    const to = state.offset + state.items.length
    const total = state.total || "?"
    count.textContent = `${from}–${to} из ${total}`
  }
}

async function openMovie(movieId) {
  try {
    const r = await safeFetch(`/movies/${movieId}?lang=ru`)
    if (r.ok) {
      const data = await r.json()
      state.selected = data
      renderDetails(data)
      return
    }
  } catch (_) {}

  const fromList = state.items.find(x => String(x.movie_id) === String(movieId))
  state.selected = fromList || { movie_id: movieId, title: "—", language: "ru" }
  renderDetails(state.selected)
}

async function loadMovies() {
  const qEl = qs("#q")
  const q = qEl ? qEl.value.trim() : ""

  const params = new URLSearchParams()
  if (q) params.set("q", q)
  params.set("limit", String(state.limit))
  params.set("offset", String(state.offset))

  try {
    const r = await safeFetch(`/movies?${params.toString()}`)
    if (!r.ok) {
      const t = await r.text()
      toast("bad", "Не удалось загрузить фильмы", `Ответ: ${r.status} ${t.slice(0, 140)}`)
      state.items = []
      state.total = 0
      renderList()
      return
    }

    const data = await r.json()

    if (Array.isArray(data)) {
      state.items = data
      state.total = data.length
    } else {
      state.items = data.items || []
      state.total = data.total ?? state.items.length
    }

    renderList()
  } catch (e) {
    toast("bad", "Failed to fetch", `Проверь API Base URL/CORS/backend. (${String(e)})`)
    state.items = []
    state.total = 0
    renderList()
  }
}

async function checkHealth() {
  const pill = qs("#statusPill")
  try {
    const r = await safeFetch(`/health`)
    if (r.ok) {
      if (pill) {
        pill.textContent = "online"
        pill.className = "pill ok"
      }
      return true
    }
  } catch (_) {}

  if (pill) {
    pill.textContent = "offline"
    pill.className = "pill bad"
  }
  return false
}

async function loadOverride() {
  const movieIdEl = qs("#ovMovieId")
  const langEl = qs("#ovLang")
  const textEl = qs("#ovText")
  const metaEl = qs("#ovMeta")

  const movieId = movieIdEl ? movieIdEl.value.trim() : ""
  const lang = langEl ? langEl.value : "ru"

  if (!movieId) {
    toast("warn", "Не хватает данных", "Укажи Movie ID")
    return
  }

  try {
    const r = await safeFetch(`/overrides/${movieId}?lang=${encodeURIComponent(lang)}`)
    if (r.ok) {
      const data = await r.json()
      if (textEl) textEl.value = data.description || ""
      if (metaEl) metaEl.textContent = `override найден, updated_at: ${data.updated_at}`
      toast("ok", "Загружено", "override подставлен в редактор")
    } else if (r.status === 404) {
      if (textEl) textEl.value = ""
      if (metaEl) metaEl.textContent = "override не найден (будет создан при сохранении)"
      toast("warn", "Нет override", "Это нормально — можешь создать новый")
    } else {
      const t = await r.text()
      toast("bad", "Ошибка", `${r.status}: ${t.slice(0, 140)}`)
    }
  } catch (e) {
    toast("bad", "Failed to fetch", String(e))
  }
}

async function saveOverride() {
  const movieIdEl = qs("#ovMovieId")
  const langEl = qs("#ovLang")
  const textEl = qs("#ovText")
  const editorEl = qs("#ovEditor")
  const metaEl = qs("#ovMeta")

  const movieId = Number(movieIdEl ? movieIdEl.value.trim() : "")
  const language = langEl ? langEl.value : "ru"
  const description = (textEl ? textEl.value : "").trim()
  const editor_id = (editorEl ? editorEl.value : "").trim() || null

  if (!movieId || !description) {
    toast("warn", "Не хватает данных", "Нужен Movie ID и описание")
    return
  }

  try {
    const r = await safeFetch(`/overrides`, {
      method: "POST",
      body: JSON.stringify({ movie_id: movieId, language, description, editor_id }),
    })
    if (!r.ok) {
      const t = await r.text()
      toast("bad", "Не сохранено", `${r.status}: ${t.slice(0, 140)}`)
      return
    }
    if (metaEl) metaEl.textContent = `сохранено, movie_id=${movieId}, lang=${language}`
    toast("ok", "Сохранено", "Override записан в базу")
  } catch (e) {
    toast("bad", "Failed to fetch", String(e))
  }
}

async function obsGet(path) {
  const out = qs("#obsOut")
  try {
    const r = await safeFetch(path, { headers: { "Content-Type": "text/plain" } })
    const text = await r.text()
    if (out) out.textContent = `GET ${path}\n\n${text}`
    toast("ok", "Успешно", `${path} ответил`)
  } catch (e) {
    if (out) out.textContent = `GET ${path}\n\n${String(e)}`
    toast("bad", "Ошибка", String(e))
  }
}

function init() {
  // Навигация
  document.querySelectorAll(".navItem").forEach(b => b.onclick = () => setRoute(b.dataset.route))

  // Health
  const checkBtn = qs("#checkHealth")
  if (checkBtn) {
    checkBtn.onclick = async () => {
      const ok = await checkHealth()
      toast(ok ? "ok" : "bad", "/health", ok ? "backend жив" : "backend недоступен")
    }
  }

  // Поиск
  const qEl = qs("#q")
  if (qEl) {
    qEl.addEventListener("input", () => {
      clearTimeout(state.debounce)
      state.debounce = setTimeout(() => { state.offset = 0; loadMovies() }, 350)
    })
  }

  const clearBtn = qs("#clear")
  if (clearBtn) {
    clearBtn.onclick = () => {
      if (qEl) qEl.value = ""
      state.offset = 0
      loadMovies()
    }
  }

  // Пагинация
  const prevBtn = qs("#prev")
  if (prevBtn) prevBtn.onclick = () => { state.offset = Math.max(0, state.offset - state.limit); loadMovies() }

  const nextBtn = qs("#next")
  if (nextBtn) nextBtn.onclick = () => { state.offset = state.offset + state.limit; loadMovies() }

  // Override
  const ovLoadBtn = qs("#ovLoad")
  if (ovLoadBtn) ovLoadBtn.onclick = loadOverride

  const ovSaveBtn = qs("#ovSave")
  if (ovSaveBtn) ovSaveBtn.onclick = saveOverride

  // Obs
  const btnPing = qs("#btnPing")
  if (btnPing) btnPing.onclick = () => obsGet("/ping")

  const btnHealth = qs("#btnHealth")
  if (btnHealth) btnHealth.onclick = () => obsGet("/health")

  const btnMetrics = qs("#btnMetrics")
  if (btnMetrics) btnMetrics.onclick = () => obsGet("/metrics")

  const runChecks = qs("#runChecks")
  if (runChecks) {
    runChecks.onclick = async () => {
      const ok = await checkHealth()
      const pingEl = qs("#statPing")
      if (pingEl) pingEl.textContent = ok ? "ok" : "fail"
      try {
        const r = await safeFetch("/metrics")
        const mEl = qs("#statMetrics")
        if (mEl) mEl.textContent = r.ok ? "ok" : "fail"
      } catch (_) {
        const mEl = qs("#statMetrics")
        if (mEl) mEl.textContent = "fail"
      }
      const tEl = qs("#statTracing")
      if (tEl) tEl.textContent = "см. Jaeger"
      toast("ok", "Проверка", "Готово")
    }
  }

  setRoute("catalog")
  checkHealth()
  loadMovies()
}

init()
