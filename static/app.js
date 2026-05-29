const state = {
  fonts: [],
  activeFont: null,
  activeTab: "isolated",
  dirtyGlyphs: new Map(),
};

const tabLabels = {
  isolated: "Persian isolated",
  initial: "Persian initial",
  medial: "Persian medial",
  final: "Persian final",
  uppercase: "English uppercase",
  lowercase: "English lowercase",
  digit: "Digits",
};

const fontsTableBody = document.getElementById("fonts-table-body");
const createForm = document.getElementById("create-font-form");
const toggleCreateButton = document.getElementById("toggle-create-button");
const cancelCreateButton = document.getElementById("cancel-create-button");
const studioPanel = document.getElementById("studio-panel");
const studioTitle = document.getElementById("studio-title");
const studioDescription = document.getElementById("studio-description");
const studioStatus = document.getElementById("studio-status");
const tabStrip = document.getElementById("tab-strip");
const glyphGrid = document.getElementById("glyph-grid");
const glyphSearch = document.getElementById("glyph-search");
const saveStudioButton = document.getElementById("save-studio-button");
const exportFontButton = document.getElementById("export-font-button");

function showStatus(message, isError = false) {
  studioStatus.textContent = message;
  studioStatus.style.color = isError ? "#b42318" : "#52607a";
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Request failed.");
  }
  return payload;
}

function toggleCreateForm(visible) {
  createForm.classList.toggle("hidden", !visible);
}

function renderFontsTable() {
  if (!state.fonts.length) {
    fontsTableBody.innerHTML =
      '<tr><td colspan="4" class="empty-state">No fonts yet. Start with “New font”.</td></tr>';
    return;
  }

  fontsTableBody.innerHTML = "";
  state.fonts.forEach((font) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>
        <strong>${escapeHtml(font.name)}</strong>
        <div class="glyph-meta">${escapeHtml(font.description || "No notes yet.")}</div>
      </td>
      <td>${new Date(font.created_at).toLocaleString()}</td>
      <td>${font.customized_glyphs}</td>
      <td>
        <div class="action-row">
          <button class="ghost" data-action="studio" data-id="${font.id}">Open studio</button>
          <button class="ghost" data-action="export" data-id="${font.id}">Export</button>
        </div>
      </td>
    `;
    fontsTableBody.appendChild(row);
  });
}

function renderTabs() {
  tabStrip.innerHTML = "";
  if (!state.activeFont) {
    return;
  }
  state.activeFont.tabs.forEach((tab) => {
    const button = document.createElement("button");
    button.className = `tab-button${state.activeTab === tab ? " active" : ""}`;
    button.textContent = tabLabels[tab] || tab;
    button.addEventListener("click", () => {
      state.activeTab = tab;
      renderStudio();
    });
    tabStrip.appendChild(button);
  });
}

function getFilteredGlyphs() {
  if (!state.activeFont) {
    return [];
  }
  const term = glyphSearch.value.trim().toLowerCase();
  return state.activeFont.glyphs.filter((glyph) => {
    const inTab = glyph.form === state.activeTab;
    const inSearch =
      !term ||
      glyph.character.toLowerCase().includes(term) ||
      glyph.id.toLowerCase().includes(term);
    return inTab && inSearch;
  });
}

function renderStudio() {
  renderTabs();
  glyphGrid.innerHTML = "";
  if (!state.activeFont) {
    return;
  }

  studioPanel.classList.remove("hidden");
  studioTitle.textContent = state.activeFont.name;
  studioDescription.textContent =
    "Edit the grid for each Persian figure or English character, then save and export the package.";
  saveStudioButton.disabled = state.dirtyGlyphs.size === 0;
  exportFontButton.disabled = false;

  const glyphs = getFilteredGlyphs();
  if (!glyphs.length) {
    glyphGrid.innerHTML = '<div class="empty-state">No glyphs match this filter.</div>';
    return;
  }

  glyphs.forEach((glyph) => {
    const card = document.createElement("article");
    card.className = `glyph-card${state.dirtyGlyphs.has(glyph.id) ? " dirty" : ""}`;

    const header = document.createElement("header");
    header.innerHTML = `
      <div>
        <h3>${escapeHtml(glyph.character)}</h3>
        <p class="glyph-meta">${escapeHtml(tabLabels[glyph.form] || glyph.form)}</p>
      </div>
      <p class="glyph-meta">${glyph.script}</p>
    `;
    card.appendChild(header);

    const canvas = document.createElement("canvas");
    canvas.className = "glyph-canvas";
    canvas.width = glyph.cols * 12;
    canvas.height = glyph.rows * 12;
    drawGlyph(canvas, glyph.cells);
    attachCanvasEditor(canvas, glyph);
    card.appendChild(canvas);

    glyphGrid.appendChild(card);
  });
}

function drawGlyph(canvas, cells) {
  const context = canvas.getContext("2d");
  const scale = canvas.width / cells[0].length;
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, canvas.width, canvas.height);

  for (let row = 0; row < cells.length; row += 1) {
    for (let col = 0; col < cells[row].length; col += 1) {
      context.fillStyle = cells[row][col] ? "#172554" : "#ffffff";
      context.fillRect(col * scale, row * scale, scale, scale);
      context.strokeStyle = "#e7edf6";
      context.strokeRect(col * scale, row * scale, scale, scale);
    }
  }
}

function attachCanvasEditor(canvas, glyph) {
  const scale = canvas.width / glyph.cols;
  let isDrawing = false;
  let drawValue = 1;

  const updateCell = (event) => {
    const rect = canvas.getBoundingClientRect();
    const col = Math.floor((event.clientX - rect.left) / (rect.width / glyph.cols));
    const row = Math.floor((event.clientY - rect.top) / (rect.height / glyph.rows));
    if (row < 0 || row >= glyph.rows || col < 0 || col >= glyph.cols) {
      return;
    }
    glyph.cells[row][col] = drawValue;
    state.dirtyGlyphs.set(glyph.id, { cells: glyph.cells });
    drawGlyph(canvas, glyph.cells, scale);
    saveStudioButton.disabled = false;
    canvas.closest(".glyph-card").classList.add("dirty");
  };

  canvas.addEventListener("pointerdown", (event) => {
    isDrawing = true;
    const rect = canvas.getBoundingClientRect();
    const col = Math.floor((event.clientX - rect.left) / (rect.width / glyph.cols));
    const row = Math.floor((event.clientY - rect.top) / (rect.height / glyph.rows));
    drawValue = glyph.cells[row][col] ? 0 : 1;
    updateCell(event);
  });

  canvas.addEventListener("pointermove", (event) => {
    if (isDrawing) {
      updateCell(event);
    }
  });

  const stopDrawing = () => {
    isDrawing = false;
  };

  canvas.addEventListener("pointerup", stopDrawing);
  canvas.addEventListener("pointerleave", stopDrawing);
}

async function loadFonts() {
  const payload = await requestJson("/api/fonts");
  state.fonts = payload.fonts;
  renderFontsTable();
}

async function openStudio(fontId) {
  const font = await requestJson(`/api/fonts/${fontId}`);
  state.activeFont = font;
  state.dirtyGlyphs.clear();
  state.activeTab = state.activeFont.tabs.includes(state.activeTab)
    ? state.activeTab
    : state.activeFont.tabs[0];
  renderStudio();
  showStatus(`Loaded ${font.name}. Edit cells and save when ready.`);
}

async function createFont(event) {
  event.preventDefault();
  const formData = new FormData(createForm);
  const payload = {
    name: formData.get("name"),
    description: formData.get("description"),
  };
  const font = await requestJson("/api/fonts", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  createForm.reset();
  toggleCreateForm(false);
  await loadFonts();
  await openStudio(font.id);
}

async function saveStudio() {
  if (!state.activeFont || state.dirtyGlyphs.size === 0) {
    return;
  }
  showStatus("Saving studio changes...");
  const glyphs = Object.fromEntries(state.dirtyGlyphs.entries());
  const font = await requestJson(`/api/fonts/${state.activeFont.id}/glyphs`, {
    method: "PUT",
    body: JSON.stringify({ glyphs }),
  });
  state.activeFont = font;
  state.dirtyGlyphs.clear();
  await loadFonts();
  renderStudio();
  showStatus("Studio saved. You can now export the font package.");
}

function exportActiveFont() {
  if (!state.activeFont) {
    return;
  }
  window.location.href = `/api/fonts/${state.activeFont.id}/export`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

fontsTableBody.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-id]");
  if (!button) {
    return;
  }
  const { action, id } = button.dataset;
  if (action === "studio") {
    await openStudio(id);
  }
  if (action === "export") {
    window.location.href = `/api/fonts/${id}/export`;
  }
});

toggleCreateButton.addEventListener("click", () => toggleCreateForm(true));
cancelCreateButton.addEventListener("click", () => toggleCreateForm(false));
createForm.addEventListener("submit", (event) => {
  createFont(event).catch((error) => showStatus(error.message, true));
});
glyphSearch.addEventListener("input", renderStudio);
saveStudioButton.addEventListener("click", () => {
  saveStudio().catch((error) => showStatus(error.message, true));
});
exportFontButton.addEventListener("click", exportActiveFont);

loadFonts().catch((error) => showStatus(error.message, true));
