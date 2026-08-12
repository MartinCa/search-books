"use strict";

const form = document.getElementById("search-form");
const input = document.getElementById("query");
const resultsEl = document.getElementById("results");
const shelfmarkLink = document.getElementById("shelfmark-link");
const submitButton = form.querySelector("button[type=submit]");

/** Build an element with text content, avoiding innerHTML entirely. */
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null && text !== "") node.textContent = text;
  return node;
}

function metaLine(book) {
  const parts = [];
  if (book.authors.length) parts.push(book.authors.join(", "));
  if (book.series) parts.push(book.series_index ? `${book.series} #${book.series_index}` : book.series);
  if (book.year) parts.push(book.year);
  if (book.narrators.length) parts.push(`Read by ${book.narrators.join(", ")}`);
  return parts.join(" · ");
}

function renderBook(book) {
  const li = el("li");

  // The cover box is always present, so a missing image never collapses the grid.
  const coverBox = el("div", "cover");
  if (book.cover_url) {
    const img = document.createElement("img");
    img.src = book.cover_url;
    img.alt = "";
    img.loading = "lazy";
    img.addEventListener("error", () => img.remove());
    coverBox.append(img);
  }
  li.append(coverBox);

  const body = el("div");
  const title = book.item_url ? el("a", "title", book.title) : el("span", "title", book.title);
  if (book.item_url) {
    title.href = book.item_url;
    title.target = "_blank";
    title.rel = "noopener";
  }
  body.append(title);

  if (book.subtitle) body.append(el("p", "meta", book.subtitle));

  const meta = metaLine(book);
  if (meta) body.append(el("p", "meta", meta));

  if (book.formats.length) {
    const tags = el("div", "tags");
    for (const format of book.formats) tags.append(el("span", "tag", format));
    body.append(tags);
  }

  li.append(body);
  return li;
}

function renderSource(source) {
  const section = el("section", "source");

  const heading = el("h2", null, source.label);
  const badge = el("span", "badge");
  if (source.status === "ok") {
    badge.textContent = String(source.count);
    badge.classList.add(source.count > 0 ? "has-results" : "empty");
  } else {
    badge.textContent = source.status === "disabled" ? "off" : "!";
    if (source.status === "error") badge.classList.add("empty");
  }
  heading.append(badge);
  section.append(heading);

  if (source.status === "disabled") {
    section.append(el("p", "state", `${source.label} is not configured.`));
  } else if (source.status === "error") {
    section.append(el("p", "state error", `${source.label} could not be searched: ${source.error}`));
  } else if (source.count === 0) {
    section.append(el("p", "state", `Not found in ${source.label}.`));
  } else {
    const list = el("ol", "books");
    for (const book of source.results) list.append(renderBook(book));
    section.append(list);
  }

  return section;
}

function render(payload) {
  resultsEl.replaceChildren(...payload.sources.map(renderSource));

  if (shelfmarkLink) {
    if (payload.shelfmark_url) {
      shelfmarkLink.href = payload.shelfmark_url;
      shelfmarkLink.hidden = false;
    } else {
      shelfmarkLink.hidden = true;
    }
  }
}

function showMessage(message, isError) {
  resultsEl.replaceChildren(el("p", isError ? "state error" : "state", message));
}

async function search(query) {
  submitButton.disabled = true;
  showMessage(`Searching for “${query}”…`, false);

  try {
    const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || `Search failed (HTTP ${response.status})`);
    }
    render(await response.json());
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    submitButton.disabled = false;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = input.value.trim();
  if (!query) return;

  const url = new URL(window.location.href);
  url.searchParams.set("q", query);
  window.history.replaceState(null, "", url);

  search(query);
});

// A page opened with ?q= runs its search immediately, so result pages are linkable.
const initialQuery = input.value.trim();
if (initialQuery) search(initialQuery);
