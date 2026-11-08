// The YAML viewer (design_config_and_navigation.md Y2): the catalog's real cards, read from
// /catalog/ (serve.py). Each tab after the first is a step, so → and the clicker move to the
// next file; the trackpad, the scroll bar, or j and k scroll it.
(() => {
  const slide = document.querySelector(".slide.yaml-viewer");
  if (!slide) return;
  const tabs = [...slide.querySelectorAll(".yv-tabs button")];
  const panel = slide.querySelector(".yv-panel");
  const code = slide.querySelector(".yv-code");
  const cache = {};

  // One invisible step per tab after the first: the engine counts them, we show the file.
  tabs.slice(1).forEach(() => slide.insertAdjacentHTML("beforeend", '<span class="step yv-step"></span>'));
  const steps = [...slide.querySelectorAll(".yv-step")];

  const esc = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  function colour(line, inBlock) {
    if (inBlock) return `<span class="y-text">${esc(line)}</span>`;
    let html = esc(line);
    const hash = html.search(/(^|\s)#/);
    let comment = "";
    if (hash >= 0) { comment = `<span class="y-c">${html.slice(hash)}</span>`; html = html.slice(0, hash); }
    // The tags written here carry no quotes, so the string rule below cannot match them.
    html = html
      .replace(/^(\s*-?\s*)(__ref__|__type__)(:)/, '$1<span class=y-ref>$2</span>$3')
      .replace(/^(\s*-?\s*)([\w.-]+)(:)(?=\s|$)/, '$1<span class=y-k>$2</span>$3')
      .replace(/(\$\{[A-Z_]+\})/g, '<span class=y-env>$1</span>')
      .replace(/("[^"]*")/g, '<span class=y-s>$1</span>');
    return html + comment;
  }

  function render(text) {
    let block = -1; // indentation of an open block scalar (| or >-), or -1
    return text.replace(/\s+$/, "").split("\n").map((line, i) => {
      const indent = line.match(/^\s*/)[0].length;
      if (block >= 0 && line.trim() && indent <= block) block = -1;
      const html = colour(line, block >= 0);
      if (block < 0 && /:\s*[|>]-?\s*$/.test(line)) block = indent;
      return `<span class="y-line"><i>${i + 1}</i>${html || " "}</span>`;
    }).join("");
  }

  async function open(n) {
    tabs.forEach((t, i) => t.classList.toggle("on", i === n));
    const file = tabs[n].dataset.file;
    try {
      cache[file] ??= await fetch(`/catalog/${file}`).then((r) => {
        if (!r.ok) throw new Error(r.status);
        return r.text();
      });
      code.innerHTML = render(cache[file]);
    } catch {
      code.innerHTML = `<span class="y-c"># ${file} could not be read - is the deck served by make talk?</span>`;
    }
    panel.scrollTop = 0;
  }

  // The engine tells us when a step is shown or hidden; the file is the number of steps shown.
  const sync = () => open(steps.filter((s) => s.classList.contains("shown")).length);
  slide.addEventListener("shown", sync);
  slide.addEventListener("steps", sync);

  tabs.forEach((tab, n) => tab.addEventListener("click", () => {
    steps.forEach((s, i) => s.classList.toggle("shown", i < n));
    open(n);
    tab.blur();
  }));

  document.addEventListener("keydown", (e) => {
    if (!slide.classList.contains("current")) return;
    if (e.key === "j" || e.key === "k") {
      panel.scrollBy({ top: e.key === "j" ? 180 : -180, behavior: "smooth" });
      e.preventDefault();
    }
  });
})();
