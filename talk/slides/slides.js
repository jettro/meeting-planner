// The slide engine: a fixed 1920x1080 canvas, keys, steps and the URL (design_slides.md S1-S6).
(() => {
  const W = 1920, H = 1080;
  const deck = document.querySelector(".deck");
  const slides = [...document.querySelectorAll(".slide")];
  const total = slides.length;
  let index = 0;

  function fit() {
    const scale = Math.min(window.innerWidth / W, window.innerHeight / H);
    deck.style.transform = `translate(-50%, -50%) scale(${scale})`;
  }

  const steps = (slide) => [...slide.querySelectorAll(".step")];

  // Demo slides (S10): the page loads the first time its slide is shown, and then stays, so a
  // demo keeps its state when you step away and come back. data-zoom makes the page bigger.
  // In still mode the slide shows its screenshot (data-still) instead, and the page is not loaded
  // until still mode is turned off (design_config_and_navigation.md Q4).
  function loadDemo(slide) {
    if (!slide.classList.contains("demo")) return;
    const src = slide.dataset.src, zoom = parseFloat(slide.dataset.zoom || "1");
    if (!slide.querySelector(".bar")) {
      const shot = slide.dataset.still
        ? `<img class="still-img" src="${slide.dataset.still}" alt="A screenshot of ${src}"
             onerror="this.outerHTML='<div class=&quot;still-img none&quot;>no still yet for ${src}</div>'">`
        : `<div class="still-img none">no still for ${src}</div>`;
      slide.insertAdjacentHTML("afterbegin", `
        <div class="bar" title="Click the bar to give the keys back to the slides">
          <span class="live">● live</span><span class="still-label">● still</span><span>${src}</span>
          <span class="hint">click this bar, then use the keys</span>
          <a href="${src}" target="_blank" rel="noopener">open in a tab ↗</a>
          <button class="nav" data-go="back" aria-label="Previous slide">‹</button>
          <button class="nav" data-go="forward" aria-label="Next slide">›</button>
        </div>
        <div class="frame">${shot}</div>`);
      // A page in a frame keeps the keys once it is clicked, and the deck cannot listen inside
      // it. Any click on the bar takes them back; the two buttons also move on.
      slide.querySelector(".bar").addEventListener("click", (e) => {
        if (e.target.closest("a")) return;
        slide.querySelector("iframe")?.blur();
        window.focus();
        const go = e.target.closest(".nav")?.dataset.go;
        if (go === "back") back();
        if (go === "forward") forward();
        e.target.closest(".nav")?.blur(); // so space and Enter do not press the button again
      });
    }
    if (still || slide.querySelector("iframe")) return;
    slide.querySelector(".frame").insertAdjacentHTML("afterbegin", `<iframe src="${src}" title="Live demo"></iframe>`);
    // The canvas is fixed (S2), so the frame is the canvas minus the 64 px bar.
    // data-width: a frame that takes only part of the canvas, beside the slide's own content.
    const iframe = slide.querySelector("iframe");
    const width = parseFloat(slide.dataset.width || W);
    iframe.style.width = `${width / zoom}px`;
    iframe.style.height = `${(H - 64) / zoom}px`;
    iframe.style.transform = `scale(${zoom})`;
  }

  // Speaker notes (S7, S8): one panel on the slide, shown with `n` or the small button, and kept
  // open or closed from slide to slide. No second window - the notes are a safety net.
  deck.insertAdjacentHTML("beforeend", `
    <div class="controls">
      <button class="notes-toggle" title="Speaker notes (n)">notes</button>
      <button class="fast-toggle" title="Fast: every slide appears whole (a)">fast</button>
      <button class="still-toggle" title="Still: screenshots instead of the live demos (s)">still</button>
      <button class="overview-toggle" title="All slides (o)">slides</button>
    </div>
    <div class="notes-panel" hidden></div>`);
  const notesPanel = deck.querySelector(".notes-panel");
  const notesToggle = deck.querySelector(".notes-toggle");
  const fastToggle = deck.querySelector(".fast-toggle");
  const stillToggle = deck.querySelector(".still-toggle");
  const overviewToggle = deck.querySelector(".overview-toggle");

  // Still mode: every live slide shows its screenshot. Remembered like fast mode - check it is
  // off before the talk, unless the demo cannot run.
  let still = false;
  try { still = localStorage.getItem("slides-still") === "1"; } catch {}
  function applyStill() {
    deck.classList.toggle("still", still);
    stillToggle.classList.toggle("on", still);
  }
  function toggleStill() {
    still = !still;
    try { localStorage.setItem("slides-still", still ? "1" : "0"); } catch {}
    applyStill();
    loadDemo(slides[index]);
  }
  applyStill();
  stillToggle.addEventListener("click", () => { toggleStill(); stillToggle.blur(); });

  // Fast mode (S15): no steps - a slide appears whole and the next key goes to the next slide.
  // Remembered in this browser only, for a run-through; a failed storage call just means off.
  let fast = false;
  try { fast = localStorage.getItem("slides-fast") === "1"; } catch {}
  fastToggle.classList.toggle("on", fast);
  function toggleFast() {
    fast = !fast;
    fastToggle.classList.toggle("on", fast);
    try { localStorage.setItem("slides-fast", fast ? "1" : "0"); } catch {}
    if (fast) steps(slides[index]).forEach((el) => el.classList.add("shown"));
    stepped();
  }
  fastToggle.addEventListener("click", () => { toggleFast(); fastToggle.blur(); });
  function showNotes() {
    const notes = slides[index].querySelector(".notes");
    notesPanel.innerHTML = notes ? notes.innerHTML : "<em>No notes for this slide.</em>";
  }
  function toggleNotes() {
    notesPanel.hidden = !notesPanel.hidden;
    notesToggle.classList.toggle("on", !notesPanel.hidden);
  }
  notesToggle.addEventListener("click", () => { toggleNotes(); notesToggle.blur(); });

  function show(i, revealAll = false) {
    const previous = index;
    index = Math.max(0, Math.min(total - 1, i));
    revealAll = revealAll || fast;
    loadDemo(slides[index]);
    showNotes();
    deck.classList.toggle("on-dark", slides[index].classList.contains("dark"));
    slides.forEach((s, n) => s.classList.toggle("current", n === index));
    // Going back lands on a slide fully built; going forward starts it empty.
    steps(slides[index]).forEach((el) => el.classList.toggle("shown", revealAll));
    const counter = slides[index].querySelector(".slide-number");
    if (counter) counter.textContent = `${index + 1} / ${total}`;
    history.replaceState(null, "", `#/${index + 1}`);
    // A slide with its own animation listens for this, and is told whether it arrived built.
    if (index !== previous || !started) {
      slides[index].dispatchEvent(new CustomEvent("shown", { detail: { built: revealAll } }));
    }
    started = true;
  }
  let started = false;

  // A slide that does more than fade its steps in (the YAML viewer) listens for this.
  const stepped = () => slides[index].dispatchEvent(new CustomEvent("steps"));

  function forward() {
    const hidden = steps(slides[index]).find((el) => !el.classList.contains("shown"));
    if (hidden) { hidden.classList.add("shown"); stepped(); }
    else if (index < total - 1) show(index + 1);
  }

  function back() {
    if (fast) { if (index > 0) show(index - 1, true); return; }
    const shown = steps(slides[index]).filter((el) => el.classList.contains("shown"));
    if (shown.length) { shown[shown.length - 1].classList.remove("shown"); stepped(); }
    else if (index > 0) show(index - 1, true);
  }

  // The slide switcher (design_config_and_navigation.md §2): every slide as a preview, built
  // from copies of the slides the first time it opens. A live slide is never copied with its
  // page: its preview is its still, or a card naming it. Click, the arrows and Enter, or a
  // number and Enter go to a slide; Esc closes.
  const THUMB = 280;
  let overview = null, picked = 0, typed = "";
  function buildOverview() {
    overview = document.createElement("div");
    overview.className = "overview";
    overview.hidden = true;
    overview.innerHTML = `<div class="ov-head"><b>Slides</b><span>click · arrows and Enter · a number and Enter · Esc</span></div><div class="ov-grid"></div>`;
    const grid = overview.querySelector(".ov-grid");
    slides.forEach((slide, n) => {
      const thumb = document.createElement("button");
      thumb.className = "thumb";
      if (slide.classList.contains("extras-divider")) thumb.classList.add("break");
      thumb.innerHTML = `<div class="thumb-canvas"></div><span class="num">${n + 1}</span>`;
      const canvas = thumb.querySelector(".thumb-canvas");
      if (slide.classList.contains("demo")) {
        canvas.innerHTML = slide.dataset.still
          ? `<img src="${slide.dataset.still}" alt="" onerror="this.outerHTML='<div class=live-card>live<br>${slide.dataset.src}</div>'">`
          : `<div class="live-card">live<br>${slide.dataset.src}</div>`;
      } else {
        const copy = slide.cloneNode(true);
        copy.querySelectorAll(".notes, iframe").forEach((el) => el.remove());
        copy.querySelectorAll(".step").forEach((el) => el.classList.add("shown"));
        copy.classList.add("current");
        const inner = document.createElement("div");
        inner.className = "deck thumb-deck";
        inner.style.transform = `scale(${THUMB / W})`;
        inner.appendChild(copy);
        canvas.appendChild(inner);
      }
      thumb.addEventListener("click", () => { closeOverview(); show(n, true); });
      grid.appendChild(thumb);
    });
    document.body.appendChild(overview);
  }
  function mark() {
    overview.querySelectorAll(".thumb").forEach((t, n) => {
      t.classList.toggle("picked", n === picked);
      t.classList.toggle("here", n === index);
    });
    overview.querySelectorAll(".thumb")[picked].scrollIntoView({ block: "nearest" });
  }
  function openOverview() {
    if (!overview) buildOverview();
    picked = index; typed = "";
    overview.hidden = false;
    mark();
  }
  function closeOverview() { if (overview) overview.hidden = true; }
  const overviewOpen = () => overview && !overview.hidden;
  function overviewKey(e) {
    // As many to a row as fit the window: count the previews on the first row.
    const thumbs = [...overview.querySelectorAll(".thumb")];
    const perRow = thumbs.filter((t) => t.offsetTop === thumbs[0].offsetTop).length;
    const move = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: perRow, ArrowUp: -perRow }[e.key];
    if (move) { picked = Math.max(0, Math.min(total - 1, picked + move)); typed = ""; mark(); }
    else if (/^[0-9]$/.test(e.key)) {
      typed += e.key;
      const n = parseInt(typed, 10) - 1;
      if (n >= 0 && n < total) { picked = n; mark(); }
    } else if (e.key === "Enter") { closeOverview(); show(picked, true); }
    else if (e.key === "Escape" || e.key === "o") closeOverview();
    else return;
    e.preventDefault();
  }
  overviewToggle.addEventListener("click", () => { openOverview(); overviewToggle.blur(); });

  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, textarea, iframe")) return;
    if (overviewOpen()) { overviewKey(e); return; }
    switch (e.key) {
      case "ArrowRight": case "ArrowDown": case " ": case "PageDown": forward(); break;
      case "ArrowLeft": case "ArrowUp": case "PageUp": back(); break;
      case "Home": show(0); break;
      case "End": show(total - 1, true); break;
      case "n": toggleNotes(); break;
      case "a": toggleFast(); break;
      case "s": toggleStill(); break;
      case "o": openOverview(); break;
      case "f":
        if (document.fullscreenElement) document.exitFullscreen();
        else document.documentElement.requestFullscreen();
        break;
      default: return;
    }
    e.preventDefault();
  });

  window.addEventListener("resize", fit);
  window.addEventListener("hashchange", () => show(parseInt(location.hash.slice(2), 10) - 1 || 0));

  // Every slide but the first gets the footer.
  const title = document.title;
  slides.slice(1).forEach((s) => {
    const footer = document.createElement("footer");
    footer.innerHTML = `<span>${title}</span><span class="slide-number"></span>`;
    s.appendChild(footer);
  });

  fit();
  show((parseInt(location.hash.slice(2), 10) || 1) - 1);
})();
