// The repository slide: the crew "arranges" the link the way it arranges a meeting, and - like
// every real booking - nothing is shown before the human approves. The approval is the slide's
// one step (→), so the presenter is the @Human.
(() => {
  const slide = document.querySelector(".slide.repo");
  if (!slide) return;

  const lines = [
    ["@Human", "@Coordinator", "Where can they find the code?"],
    ["@Coordinator", "@FacilityManager", "FindLocationAssignment \"somewhere they can clone it\""],
    ["@FacilityManager", "", "reading the descriptions… 3 rooms, 1 repository"],
    ["@FacilityManager", "@Coordinator", "LocationFound go.jettro.dev/pulse - \"short, quiet, free\""],
    ["@Catering", "@FacilityManager", "Shall I order lunch with that?"],
    ["@FacilityManager", "@Catering", "No."],
    ["@Coordinator", "@Human", "ApprovalRequest - show it to the room?"],
  ];

  const trace = slide.querySelector(".repo-trace");
  trace.innerHTML = lines.map(([from, to, what]) => `
    <div class="line"><span class="who">${from}</span>${to ? ` → <span class="who">${to}</span>` : ""}
      <span class="what">${what}</span></div>`).join("");
  const rows = [...trace.querySelectorAll(".line")];
  const gate = slide.querySelector(".gate");

  let timers = [];
  slide.addEventListener("shown", (e) => {
    timers.forEach(clearTimeout);
    timers = [];
    const built = e.detail.built;
    rows.forEach((r) => r.classList.toggle("in", built));
    gate.classList.toggle("in", built);
    if (built) return;
    // One message every 0.9 s, then the question waits for the human.
    rows.forEach((r, i) => timers.push(setTimeout(() => r.classList.add("in"), 600 + i * 900)));
    timers.push(setTimeout(() => gate.classList.add("in"), 600 + rows.length * 900));
  });
})();
