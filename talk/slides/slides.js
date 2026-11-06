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
  function loadDemo(slide) {
    if (!slide.classList.contains("demo") || slide.querySelector("iframe")) return;
    const src = slide.dataset.src, zoom = parseFloat(slide.dataset.zoom || "1");
    slide.insertAdjacentHTML("afterbegin", `
      <div class="bar" title="Click the bar to give the keys back to the slides">
        <span class="live">● live</span><span>${src}</span>
        <span class="hint">click this bar, then use the keys</span>
        <a href="${src}" target="_blank" rel="noopener">open in a tab ↗</a>
        <button class="nav" data-go="back" aria-label="Previous slide">‹</button>
        <button class="nav" data-go="forward" aria-label="Next slide">›</button>
      </div>
      <div class="frame"><iframe src="${src}" title="Live demo"></iframe></div>`);
    // The canvas is fixed (S2), so the frame is the canvas minus the 64 px bar.
    // data-width: a frame that takes only part of the canvas, beside the slide's own content.
    const iframe = slide.querySelector("iframe");
    const width = parseFloat(slide.dataset.width || W);
    iframe.style.width = `${width / zoom}px`;
    iframe.style.height = `${(H - 64) / zoom}px`;
    iframe.style.transform = `scale(${zoom})`;
    // A page in a frame keeps the keys once it is clicked, and the deck cannot listen inside it.
    // Any click on the bar takes them back; the two buttons also move on.
    slide.querySelector(".bar").addEventListener("click", (e) => {
      if (e.target.closest("a")) return;
      iframe.blur();
      window.focus();
      const go = e.target.closest(".nav")?.dataset.go;
      if (go === "back") back();
      if (go === "forward") forward();
      e.target.closest(".nav")?.blur(); // so space and Enter do not press the button again
    });
  }

  // Speaker notes (S7, S8): one panel on the slide, shown with `n` or the small button, and kept
  // open or closed from slide to slide. No second window - the notes are a safety net.
  deck.insertAdjacentHTML("beforeend", `
    <div class="controls">
      <button class="notes-toggle" title="Speaker notes (n)">notes</button>
      <button class="fast-toggle" title="Fast: every slide appears whole (a)">fast</button>
    </div>
    <div class="notes-panel" hidden></div>`);
  const notesPanel = deck.querySelector(".notes-panel");
  const notesToggle = deck.querySelector(".notes-toggle");
  const fastToggle = deck.querySelector(".fast-toggle");

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

  function forward() {
    const hidden = steps(slides[index]).find((el) => !el.classList.contains("shown"));
    if (hidden) hidden.classList.add("shown");
    else if (index < total - 1) show(index + 1);
  }

  function back() {
    if (fast) { if (index > 0) show(index - 1, true); return; }
    const shown = steps(slides[index]).filter((el) => el.classList.contains("shown"));
    if (shown.length) shown[shown.length - 1].classList.remove("shown");
    else if (index > 0) show(index - 1, true);
  }

  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, textarea, iframe")) return;
    switch (e.key) {
      case "ArrowRight": case "ArrowDown": case " ": case "PageDown": forward(); break;
      case "ArrowLeft": case "ArrowUp": case "PageUp": back(); break;
      case "Home": show(0); break;
      case "End": show(total - 1, true); break;
      case "n": toggleNotes(); break;
      case "a": toggleFast(); break;
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
