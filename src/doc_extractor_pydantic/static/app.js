const form = document.querySelector("#extract-form");
const input = document.querySelector("#document");
const submit = document.querySelector("#submit");
const status = document.querySelector("#status");
const introCopy = document.querySelector("#intro-copy");
const uploadLabel = document.querySelector("#upload-label");
const result = document.querySelector("#result");
const imagePreview = document.querySelector("#image-preview");
const focusPanel = document.querySelector("#focus-panel");
const focusEmpty = document.querySelector("#focus-empty");
const focusLabel = document.querySelector("#focus-label");
const focusImageContainer = document.querySelector("#focus-image-container");
const focusImage = document.querySelector("#focus-image");
const focusThumbnails = document.querySelector("#focus-thumbnails");
const summary = document.querySelector("#summary");
const warningBox = document.querySelector("#warning-box");
const warnings = document.querySelector("#warnings");
const fields = document.querySelector("#fields");
const rawText = document.querySelector("#raw-text");
let lastData = null;
let previewUrl = null;
let selectedIsPdf = false;
let requestId = 0;
let pendingRequest = null;
const focusState = { previews: [], index: 0, kind: "unknown" };

function syncResultHeight() {
  if (result.classList.contains("hidden")) return;
  if (window.matchMedia("(max-width: 800px)").matches) {
    result.style.removeProperty("--result-height");
    return;
  }
  const top = result.getBoundingClientRect().top;
  const available = Math.max(240, Math.floor(window.innerHeight - top - 24));
  result.style.setProperty("--result-height", `${available}px`);
}

function fitFocusImage(preview) {
  const sourceWidth = focusImage.naturalWidth || Number(preview?.sourceWidth);
  const sourceHeight = focusImage.naturalHeight || Number(preview?.sourceHeight);
  const aspectRatio = sourceWidth && sourceHeight ? sourceWidth / sourceHeight : 0;
  const isCardDocument = aspectRatio >= 1.25
    && aspectRatio <= 1.75;
  const isSmallSquare = aspectRatio > 0
    && Math.abs(aspectRatio - 1) < 0.08
    && sourceWidth < 700;
  const shouldFit = isCardDocument || isSmallSquare;
  focusImageContainer.classList.toggle("focus-fit", shouldFit);
  focusImage.classList.toggle("focus-image-qr", shouldFit && isSmallSquare);
  const containerWidth = focusImageContainer.clientWidth;
  if (!sourceWidth || !sourceHeight || !containerWidth) {
    focusImageContainer.style.removeProperty("height");
    return;
  }
  const resultHeight = result.clientHeight || window.innerHeight;
  const availableHeight = Math.max(220, Math.min(520, resultHeight - 176)) * 0.9;
  const maxHeight = isSmallSquare
    ? Math.min(300, availableHeight)
    : availableHeight;
  if (!shouldFit) {
    focusImageContainer.style.height = `${Math.round(availableHeight)}px`;
    return;
  }
  const targetHeight = Math.min(
    maxHeight,
    Math.max(220, containerWidth / aspectRatio),
  );
  focusImageContainer.style.height = `${Math.round(targetHeight)}px`;
}

window.addEventListener("resize", () => {
  syncResultHeight();
  renderFocusPreview();
});

focusImage.addEventListener("load", () => {
  fitFocusImage(focusState.previews[focusState.index]);
});

input.addEventListener("change", () => {
  const file = input.files?.[0];
  if (!file) return;
  requestId += 1;
  if (pendingRequest) pendingRequest.abort();
  pendingRequest = null;
  submit.disabled = false;
  lastData = null;
  document.body.classList.remove("has-result");
  result.classList.add("hidden");
  summary.textContent = "";
  warningBox.classList.add("hidden");
  warnings.replaceChildren();
  fields.replaceChildren();
  rawText.textContent = "";
  status.className = "status";
  status.textContent = "";
  focusState.previews = [];
  focusState.index = 0;
  focusState.kind = "unknown";
  result.style.removeProperty("--result-height");
  focusImageContainer.style.removeProperty("height");
  focusPanel.classList.add("hidden");
  focusEmpty.classList.add("hidden");
  focusThumbnails.replaceChildren();
  focusImage.removeAttribute("src");
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(file);
  const isImage = file.type.startsWith("image/") || /\.(jpe?g|png)$/i.test(file.name);
  selectedIsPdf = file.type === "application/pdf" || /\.pdf$/i.test(file.name);
  imagePreview.classList.toggle("hidden", !isImage);
  if (isImage) imagePreview.src = previewUrl;
});

function renderFocusPreview() {
  const preview = focusState.previews[focusState.index];
  if (!preview) return;
  focusLabel.textContent = preview.label || "Detalhe do documento";
  if (focusImage.getAttribute("src") !== preview.src) {
    focusImage.src = preview.src;
  }
  fitFocusImage(preview);
  [...focusThumbnails.children].forEach((thumbnail, index) => {
    thumbnail.classList.toggle("selected", index === focusState.index);
  });
}

function renderFocusPreviews(previews, kind) {
  focusState.previews = previews || [];
  focusState.index = 0;
  focusState.kind = kind || "unknown";
  focusThumbnails.replaceChildren();
  if (!focusState.previews.length) {
    focusPanel.classList.add("hidden");
    focusEmpty.classList.toggle("hidden", !selectedIsPdf);
  focusImage.removeAttribute("src");
  focusImage.classList.remove("focus-image-qr");
  focusImageContainer.classList.remove("focus-fit");
    focusImageContainer.style.removeProperty("height");
    return;
  }
  focusPanel.classList.remove("hidden");
  focusEmpty.classList.add("hidden");
  focusState.previews.forEach((preview, index) => {
    const thumbnail = document.createElement("button");
    thumbnail.type = "button";
    thumbnail.className = "focus-thumb";
    thumbnail.title = preview.label || `Detalhe ${index + 1}`;
    const image = document.createElement("img");
    image.src = preview.src;
    image.alt = preview.label || `Detalhe ${index + 1}`;
    thumbnail.append(image);
    thumbnail.addEventListener("click", () => {
      focusState.index = index;
      renderFocusPreview();
    });
    focusThumbnails.append(thumbnail);
  });
  renderFocusPreview();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!input.files?.[0]) return;
  submit.disabled = true;
  status.className = "status";
  status.textContent = "Analisando seu documento...";
  document.body.classList.remove("has-result");
  result.classList.add("hidden");
  requestId += 1;
  const currentRequest = requestId;
  if (pendingRequest) pendingRequest.abort();
  const controller = new AbortController();
  pendingRequest = controller;
  try {
    const response = await fetch("/api/extract", { method: "POST", body: new FormData(form), signal: controller.signal });
    const data = await response.json();
    if (currentRequest !== requestId) return;
    if (!response.ok) throw new Error(data.detail || "Não foi possível analisar o documento.");
    lastData = data;
    renderResult(data);
    status.textContent = "Tudo certo! Confira as informações antes de copiar.";
  } catch (error) {
    if (currentRequest !== requestId || error.name === "AbortError") return;
    status.className = "status error";
    status.textContent = error.message;
  } finally {
    if (currentRequest === requestId) {
      pendingRequest = null;
      submit.disabled = false;
    }
  }
});

const confidenceLabels = { medium: "conferir", low: "conferir com atenção" };
const confidenceHints = {
  medium: "O modelo leu este dado com pequena incerteza.",
  low: "O modelo leu este dado parcialmente. Compare com o documento.",
};

function renderFieldCard(key, value) {
  const card = document.createElement("div");
  card.className = "field-card";
  card.dataset.fieldLabel = key;
  card.dataset.found = value.value ? "true" : "false";
  const name = document.createElement("span");
  name.className = "field-name";
  const nameText = document.createElement("span");
  nameText.textContent = value.label;
  name.append(nameText);
  const confidence = confidenceLabels[value.confidence];
  if (value.value && confidence) {
    const badge = document.createElement("span");
    badge.className = "field-confidence";
    badge.dataset.confidence = value.confidence;
    badge.textContent = confidence;
    badge.title = confidenceHints[value.confidence];
    name.append(badge);
  }
  const fieldValue = document.createElement("span");
  fieldValue.className = "field-value";
  fieldValue.textContent = value.value || "Não identificado";
  const control = document.createElement("div"); control.className = "field-control";
  const copyButton = document.createElement("button");
  copyButton.type = "button";
  copyButton.className = "secondary field-copy";
  copyButton.title = `Copiar ${value.label}`;
  copyButton.setAttribute("aria-label", `Copiar ${value.label}`);
  copyButton.innerHTML = '<svg class="copy-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="11" height="11" rx="2"></rect><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"></path></svg>';
  copyButton.disabled = !value.value;
  copyButton.addEventListener("click", async () => {
    if (await copyText(value.value || "")) status.textContent = `${value.label} copiado.`;
  });
  control.append(fieldValue, copyButton); card.append(name, control); return card;
}

function renderResult(data) {
  result.classList.remove("hidden");
  document.body.classList.add("has-result");
  document.body.classList.add("has-extracted");
  introCopy.classList.add("hidden");
  uploadLabel.classList.remove("hidden");
  syncResultHeight();
  const kindLabels = { cnh: "CNH", rg: "RG", unknown: "documento" };
  const kindLabel = kindLabels[data.kind] || "documento";
  const pageLabel = data.pages === 1 ? "1 página" : `${data.pages} páginas`;
  summary.textContent = data.kind === "unknown"
    ? `Não foi possível identificar o documento • ${pageLabel}`
    : `${kindLabel} identificado • ${pageLabel}`;
  rawText.textContent = data.text || "Nenhum texto foi encontrado.";
  renderFocusPreviews(data.previews, data.kind);
  const warningItems = Array.isArray(data.warnings)
    ? data.warnings.filter((warning) => typeof warning === "string" && warning.trim())
    : [];
  warningBox.classList.toggle("hidden", !warningItems.length);
  warnings.replaceChildren(...warningItems.map((warning) => {
    const li = document.createElement("li"); li.textContent = warning; return li;
  }));
  const found = Object.entries(data.fields || {}).map(([key, value]) => renderFieldCard(key, value));
  const missing = (Array.isArray(data.missing) ? data.missing : [])
    .map((field) => renderFieldCard(field.key, { label: field.label, value: null }));
  fields.replaceChildren(...found, ...missing);
  syncResultHeight();
}

async function copyText(value) {
  try {
    await navigator.clipboard.writeText(value);
    status.className = "status";
    return true;
  } catch {
    status.className = "status error";
    status.textContent = "Não foi possível copiar. Selecione o texto e copie manualmente.";
    return false;
  }
}

document.querySelector("#copy").addEventListener("click", async () => {
  if (!lastData) return;
  const values = [...fields.querySelectorAll('.field-card[data-found="true"]')].map((field) => `${field.querySelector(".field-name span").textContent}: ${field.querySelector(".field-value").textContent}`);
  if (await copyText(values.join("\n"))) status.textContent = "Dados copiados. Faça a conferência final.";
});
document.querySelector("#copy-text").addEventListener("click", async () => {
  if (await copyText(rawText.textContent)) status.textContent = "Texto do documento copiado.";
});
