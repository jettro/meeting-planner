// The five team patterns as small diagrams (design_team_patterns.md, slide B).
// An agent is a circle; the one in charge is filled. Drawn here so index.html stays readable.
(() => {
  const R = 24;
  const node = ([x, y], cls = "") => `<circle class="agent ${cls}" cx="${x}" cy="${y}" r="${R}"/>`;

  // A line from the edge of one circle to the edge of the other, with or without an arrowhead.
  function link([x1, y1], [x2, y2], { arrow = true, cls = "" } = {}) {
    const d = Math.hypot(x2 - x1, y2 - y1), ux = (x2 - x1) / d, uy = (y2 - y1) / d;
    const gap = R + 6, end = arrow ? gap + 4 : gap;
    return `<line class="link ${cls}" x1="${x1 + ux * gap}" y1="${y1 + uy * gap}"
      x2="${x2 - ux * end}" y2="${y2 - uy * end}"${arrow ? ' marker-end="url(#head)"' : ""}/>`;
  }
  // A curved arrow, for a handoff: the conversation moves over.
  function curve([x1, y1], [x2, y2], bend) {
    const mx = (x1 + x2) / 2 + bend[0], my = (y1 + y2) / 2 + bend[1];
    const d1 = Math.hypot(mx - x1, my - y1), d2 = Math.hypot(x2 - mx, y2 - my);
    const sx = x1 + ((mx - x1) / d1) * (R + 6), sy = y1 + ((my - y1) / d1) * (R + 6);
    const ex = x2 - ((x2 - mx) / d2) * (R + 10), ey = y2 - ((y2 - my) / d2) * (R + 10);
    return `<path class="link dashed" d="M${sx},${sy} Q${mx},${my} ${ex},${ey}" marker-end="url(#head)"/>`;
  }

  const draw = {
    pipeline() {
      const a = [150, 40], b = [150, 150], c = [150, 260];
      return link(a, b) + link(b, c) + node(a) + node(b) + node(c);
    },
    fanout() {
      const top = [150, 36], bottom = [150, 264], mids = [[55, 150], [150, 150], [245, 150]];
      return mids.map((m) => link(top, m) + link(m, bottom)).join("")
        + node(top) + mids.map((m) => node(m)).join("") + node(bottom);
    },
    orchestrator() {
      const boss = [150, 40], workers = [[55, 150], [150, 150], [245, 150]];
      const subs = [[200, 260], [270, 260]];
      return workers.map((w) => link(boss, w, { arrow: false })).join("")
        + subs.map((s) => link(workers[2], s, { arrow: false })).join("")
        + node(boss, "lead") + workers.map((w) => node(w)).join("")
        + node(workers[2], "lead small-lead") + subs.map((s) => node(s)).join("");
    },
    handoff() {
      const a = [55, 70], b = [245, 70], c = [150, 250];
      return curve(a, b, [0, -50]) + curve(b, c, [60, 10])
        + node(a, "faded") + node(b, "faded") + node(c, "active");
    },
    groupchat() {
      const around = [[50, 45], [250, 45], [50, 255], [250, 255]];
      return around.map((p) => link(p, [150, 150], { arrow: false })).join("")
        + `<rect class="room" x="100" y="115" width="100" height="70" rx="16"/>`
        + `<text class="room-label" x="150" y="158">chat</text>`
        + around.map((p) => node(p)).join("");
    },
  };

  document.querySelectorAll(".pattern").forEach((fig) => {
    fig.querySelector(".diagram").innerHTML = `
      <svg viewBox="0 0 300 300" aria-hidden="true">
        <defs><marker id="head" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5"
          orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="head"/></marker></defs>
        ${draw[fig.dataset.pattern]()}
      </svg>`;
  });
})();
