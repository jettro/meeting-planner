// The title slide's visual: an isometric cube of nested stripes, and the team's messages
// streaming past it - a nod to the DevPulse site, drawn here rather than copied.
(() => {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.querySelector(".title-slide .cube");
  if (!svg) return;

  // One cube, three faces, seen from above. C is the front corner of the top face.
  const s = 420, a = s * Math.cos(Math.PI / 6), b = s * Math.sin(Math.PI / 6);
  const C = [400, 380];
  const pt = (dx, dy) => [C[0] + dx, C[1] + dy];
  const faces = [
    { pts: [pt(0, 0), pt(-a, -b), pt(0, -2 * b), pt(a, -b)], colours: ["#ee9a62", "#2a2026"] },      // top
    { pts: [pt(0, 0), pt(-a, -b), pt(-a, -b + s), pt(0, s)], colours: ["#6434da", "#1c1830"] },      // left
    { pts: [pt(0, 0), pt(a, -b), pt(a, -b + s), pt(0, s)], colours: ["#c4a892", "#2a2420"] },        // right
  ];

  // Each face: the polygon shrunk towards its centre, again and again, in alternating colours.
  const RINGS = 9;
  for (const face of faces) {
    const cx = face.pts.reduce((t, p) => t + p[0], 0) / 4;
    const cy = face.pts.reduce((t, p) => t + p[1], 0) / 4;
    for (let i = 0; i < RINGS; i++) {
      const k = 1 - i / RINGS;
      const poly = document.createElementNS(NS, "polygon");
      poly.setAttribute("points", face.pts.map(([x, y]) => `${cx + (x - cx) * k},${cy + (y - cy) * k}`).join(" "));
      poly.setAttribute("fill", face.colours[i % 2]);
      svg.appendChild(poly);
    }
  }

  // The messages of one meeting, as the trace shows them - rolled twice for a seamless loop.
  const messages = [
    ["@Human", "PlanMeetingRequest"],
    ["@Coordinator", "FindLocationAssignment \"somewhere quiet\""],
    ["@FacilityManager", "LocationFound Library"],
    ["@Coordinator", "FindSlotsAssignment"],
    ["@Scheduler", "SlotsFound 3"],
    ["@Coordinator", "SlotApprovalRequest"],
    ["@Human", "SlotApprovalDecision 10:00"],
    ["@Coordinator", "LunchApprovalRequest"],
    ["@Human", "\"vegetarian, no bread\""],
    ["@Coordinator", "BookMeetingAssignment"],
    ["@Scheduler", "MeetingBooked"],
    ["@Coordinator", "BookFacilitiesAssignment"],
    ["@FacilityManager", "OrderLunchAssignment"],
    ["@Catering", "LunchOrdered"],
    ["@FacilityManager", "FacilitiesBooked"],
    ["@Coordinator", "PlanCompleted"],
    ["@Intake", "look_up_people Sanne, Daan"],
    ["@FacilityManager", "MemoryApplied"],
  ];
  const roll = document.querySelector(".title-slide .trace-roll");
  const lines = messages.map(([who, what]) => `<div><span class="who">${who}</span> ${what}</div>`).join("");
  roll.innerHTML = lines + lines;
})();
