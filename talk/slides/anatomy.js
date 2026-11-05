// The anatomy of an agent, from the playful deck: one robot that gains a piece of gear per slide,
// and a diagram that grows with it. Runs before slides.js, which then adds footers and steps.
//
//   <section class="slide anatomy" data-stage="3"></section>   - stages 1 to 5
//   <section class="slide anatomy-team"></section>             - the team
(() => {
  const groups = [
    { label: "Goal", items: [["A job + a finish line", ""]] },
    { label: "LLM", items: [
      ["LLM", "propose the next action"],
      ["Prompting", "instructions and constraints"],
      ["Execution loop", "act, observe, continue or stop"],
    ] },
    { label: "Tools", items: [["Tools", "functions and APIs"], ["MCP", "one way to connect"]] },
    { label: "Context", items: [
      ["State", "current work"],
      ["Conversation", "interaction history"],
      ["Memory", "retained for later"],
      ["Knowledge base", "relevant information via retrieval"],
    ] },
    { label: "Boundaries", items: [
      ["Deterministic business rules", ""],
      ["Guardrails on inputs and actions", ""],
      ["Human approval when needed", ""],
    ] },
  ];

  const stages = [
    { title: "So… what’s my job?", takeaway: "A goal, and a way to know when it is done." },
    { title: "I have a plan. Probably.", takeaway: "The model proposes. The software runs the loop." },
    { title: "Less talking. More doing.", takeaway: "Tools turn proposed actions into actual work." },
    { title: "Wait, what were we doing?", takeaway: "Context makes the next decision less of a guessing game." },
    { title: "Who gave it the delete button?", takeaway: "The runtime enforces the boundaries." },
  ];

  const card = (g, cls) => `
    <div class="card ${cls}">
      <div class="label">${g.label}</div>
      ${g.items.map(([name, what]) =>
        `<div class="item"><b>${name}</b>${what ? ` <span>${what}</span>` : ""}</div>`).join("")}
    </div>`;

  document.querySelectorAll(".slide.anatomy").forEach((slide) => {
    const n = parseInt(slide.dataset.stage, 10);
    const stage = stages[n - 1];
    // Earlier gear is plain; the gear this slide adds is marked; later gear is not there yet.
    // Two stacked columns, so a short card never takes the height of a tall one beside it:
    // goal, tools and boundaries on the left; the LLM and context on the right.
    const column = (ids) => `<div class="column">${ids
      .map((i) => (i < n ? card(groups[i], i === n - 1 ? "new" : "") : "")).join("")}</div>`;
    const cards = column([0, 2, 4]) + column([1, 3]);
    slide.insertAdjacentHTML("afterbegin", `
      <h2>${stage.title}</h2>
      <div class="anatomy-body">
        <div class="cards">${cards}</div>
        <img class="robot" src="img/robot-${n}.png" alt="">
      </div>
      <p class="takeaway">${stage.takeaway}</p>`);
  });

  document.querySelectorAll(".slide.anatomy-team").forEach((slide) => {
    const agents = ["A", "B", "C"].map((name, i) => `
      <div class="member step">
        <img src="img/robot-${i + 3}.png" alt="">
        <div class="card"><b>Agent ${name}</b><span>own state, tools and checks</span></div>
      </div>`).join("");
    slide.insertAdjacentHTML("afterbegin", `
      <h2>Now everybody has opinions.</h2>
      <div class="team">
        <div class="you card new"><b>You</b><span>messages + routing</span></div>
        <div class="members">${agents}</div>
      </div>
      <p class="takeaway step">Independent agents, shared objective.</p>`);
  });
})();
