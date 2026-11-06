// Code on a slide (design_agent_demo.md): a few regexes colour Python, no CDN (S11).
// <pre class="code" data-new="3,5-7"> marks the lines that are new in this step.
(() => {
  const PY = new RegExp([
    /(#.*)/.source,                                        // 1 comment
    /((?:f)?"""[\s\S]*?"""|(?:f)?"(?:[^"\\\n]|\\.)*")/.source, // 2 string
    /(@[\w.]+)/.source,                                    // 3 decorator
    /\b(from|import|def|return|if|else|for|in|and|or|not|None|True|False)\b/.source, // 4 keyword
    /\b(\d+)\b/.source,                                    // 5 number
  ].join("|"), "g");
  const KIND = [null, "c", "s", "d", "k", "n"];

  const esc = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  function colour(line) {
    let out = "", last = 0;
    for (const m of line.matchAll(PY)) {
      const kind = KIND[m.slice(1).findIndex((g) => g !== undefined) + 1];
      out += esc(line.slice(last, m.index)) + `<span class="${kind}">${esc(m[0])}</span>`;
      last = m.index + m[0].length;
    }
    return out + esc(line.slice(last));
  }

  function lines(spec) {
    const set = new Set();
    for (const part of (spec || "").split(",").filter(Boolean)) {
      const [a, b] = part.split("-").map(Number);
      for (let n = a; n <= (b || a); n++) set.add(n);
    }
    return set;
  }

  document.querySelectorAll("pre.code").forEach((pre) => {
    const isNew = lines(pre.dataset.new);
    const text = pre.textContent.replace(/^\n/, "").replace(/\s+$/, "");
    pre.innerHTML = text.split("\n")
      .map((l, i) => `<span class="line${isNew.has(i + 1) ? " new" : ""}">${colour(l) || " "}</span>`)
      .join("");
  });
})();
