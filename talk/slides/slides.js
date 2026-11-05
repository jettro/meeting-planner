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

  function show(i, revealAll = false) {
    index = Math.max(0, Math.min(total - 1, i));
    slides.forEach((s, n) => s.classList.toggle("current", n === index));
    // Going back lands on a slide fully built; going forward starts it empty.
    steps(slides[index]).forEach((el) => el.classList.toggle("shown", revealAll));
    const counter = slides[index].querySelector(".slide-number");
    if (counter) counter.textContent = `${index + 1} / ${total}`;
    history.replaceState(null, "", `#/${index + 1}`);
  }

  function forward() {
    const hidden = steps(slides[index]).find((el) => !el.classList.contains("shown"));
    if (hidden) hidden.classList.add("shown");
    else if (index < total - 1) show(index + 1);
  }

  function back() {
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
