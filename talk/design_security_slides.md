# Design: two slides on security - who is the agent, when it calls?

> **Status:** built 2026-11-24 as slides 45-46, right after the guardrails (42-44). Asked for by the
> human: the challenge for one agent, and why a team makes it harder. It does not have to follow the
> sample to the letter; the notes say where the sample stands.

## The story

- **Slide 45 - Who is the agent, when it calls?** One agent, three answers side by side: *as the
  person* (pass their token on), *as itself* (one generic key), *on behalf of* (a token naming both,
  narrowed). For each: what it may do, the risk, what the log shows. The third is outlined as the
  one to aim for; the second is what you do when the system behind the MCP server knows no users.
  Underneath, two circles - *who asks* and *what it is for* - and the takeaway: *an agent's rights
  are the overlap*.
- **Slide 46 - In a team, rights travel with messages.** The chain @Human -> @Intake ->
  @Coordinator -> @FacilityManager -> location service, with a bar that narrows at each hop and the
  service asking *who is asking now?*. Then three ways it goes wrong (escalation by asking, a key in
  a message, an injection that travels) against four rules that hold (rights only narrow, a key
  stays with its agent, a request asks only what its type allows, the receiver checks). Takeaway:
  *check rights where the work is done, not where it was asked for*.

## Where the sample stands (for the notes, not the slide)

- Each specialist holds the API key of one MCP server, on its card; a test keeps it to one. The key
  is never in a message. @Intake and @Guard have no tools.
- Requests are typed messages; the booking rules check every booking call against the approval.
- The services do not know which person asks: the key is the agent's (*as itself*). On behalf of
  needs a token exchange the services do not offer yet - the next step, not built.

## Sources (checked 2026-11-24)

| Source | What it supports |
|---|---|
| MCP spec 2026-07-28, [Authorization - security considerations](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/security-considerations) | the server must not pass on the token it received; token passthrough is "explicitly forbidden"; servers must check a token was issued for them |
| MCP spec 2025-06-18, [Security best practices](https://modelcontextprotocol.io/specification/2025-06-18/basic/security_best_practices) | the confused deputy problem, and token passthrough, as named risks |
| MCP spec, [Authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization) | built on the OAuth 2.1 draft; audience checked through resource indicators (RFC 8707) |
| [RFC 8693, OAuth 2.0 Token Exchange](https://www.rfc-editor.org/rfc/rfc8693) | impersonation (A *is* B) against delegation (A acts *for* B, keeps its own identity); the `act` claim names the acting party, nested for a chain |
| OWASP, [Top 10 for LLM applications 2025](https://genai.owasp.org/llm-top-10/) - LLM06 Excessive Agency | not on the slide; a reference for questions |
| Microsoft, [Entra Agent ID](https://learn.microsoft.com/en-us/entra/agent-id/what-is-microsoft-entra-agent-id) | not on the slide; agents getting identities of their own, for questions |
