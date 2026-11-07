// One meeting, in messages (design_messages.md M4): a sequence diagram of the coordinator's saga,
// as coordinator.py sends it. Each phase is a step, so it builds up one key press at a time.
(() => {
  const host = document.querySelector(".msg-flow .seq");
  if (!host) return;

  const W = 1600, TOP = 70, ROW = 34, GAP = 10;
  const lanes = { you: 110, coord: 470, sched: 830, fm: 1170, cat: 1490 };
  const names = { you: "you", coord: "@Coordinator", sched: "@Scheduler", fm: "@FacilityManager", cat: "@Catering" };

  // [from, to, message, kind]; kind "ask" marks a message that waits for you.
  const phases = [
    [["you", "coord", "PlanMeetingRequest"]],
    [["coord", "fm", "FindLocationAssignment"], ["fm", "coord", "LocationFound"]],
    [["coord", "sched", "FindSlotsAssignment"], ["sched", "coord", "SlotsFound"]],
    [["coord", "you", "SlotApprovalRequest", "ask"], ["you", "coord", "SlotApprovalDecision", "ask"]],
    [["coord", "you", "LunchApprovalRequest", "ask"], ["you", "coord", "LunchApprovalDecision", "ask"]],
    [["coord", "sched", "BookMeetingAssignment"], ["sched", "coord", "MeetingBooked"]],
    [["coord", "fm", "BookFacilitiesAssignment"], ["fm", "cat", "OrderLunchAssignment"],
     ["cat", "fm", "LunchOrdered"], ["fm", "coord", "FacilitiesBooked"]],
    [["coord", "you", "PlanCompleted"]],
  ];

  const rows = phases.reduce((n, p) => n + p.length, 0);
  const H = TOP + rows * ROW + (phases.length - 1) * GAP + 20;

  let y = TOP, body = "";
  phases.forEach((phase, i) => {
    const arrows = phase.map(([from, to, label, kind]) => {
      y += ROW;
      const x1 = lanes[from], x2 = lanes[to], dir = Math.sign(x2 - x1);
      const mid = (x1 + x2) / 2;
      return `<g class="msg ${kind || ""}">
        <line x1="${x1 + dir * 8}" y1="${y}" x2="${x2 - dir * 14}" y2="${y}" marker-end="url(#seq-head)"/>
        <text x="${mid}" y="${y - 8}">${label}</text></g>`;
    }).join("");
    body += `<g class="${i === 0 ? "" : "step"}">${arrows}</g>`;
    y += GAP;
  });

  const heads = Object.entries(lanes).map(([k, x]) =>
    `<g class="lane ${k}"><rect x="${x - 120}" y="0" width="240" height="44" rx="10"/>
     <text x="${x}" y="30">${names[k]}</text>
     <line x1="${x}" y1="44" x2="${x}" y2="${H}"/></g>`).join("");

  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" aria-label="The messages of one meeting">
    <defs><marker id="seq-head" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6"
      orient="auto"><path d="M0,0 L10,5 L0,10 z"/></marker></defs>
    ${heads}${body}</svg>`;
})();
