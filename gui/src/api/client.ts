/**
 * Everything the browser knows about the server, in one file.
 *
 * Two shapes matter more than the rest, and both are easy to get subtly wrong:
 *
 * - A persisted event *is* a framework message. `SentMessage` wraps one of our
 *   domain messages in `.message`; the others (`StartMessage`, `EventMessage`,
 *   `ReceivedMessage`, `ProcessedMessage`) are the framework talking about
 *   itself. The conversation view is the first kind; the framework view is all
 *   of them.
 * - There are two ids on a question. The outer one belongs to the envelope and
 *   is what the client de-duplicates on. The *inner* one - `message.id` - is
 *   what an answer refers to. Sending the outer id to `/human-input` fails in
 *   the most confusing way available: the call succeeds and the team never
 *   moves.
 */

const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8200";

export const TEAM_NAMESPACE = "meeting-planner";
/** The team you talk to: @Intake in front of the same agents (design_chat.md). */
export const CHAT_NAMESPACE = "meeting-planner-chat";
export const HUMAN = "@Human";
export const COORDINATOR = "@Coordinator";
export const INTAKE = "@Intake";
/** The framework's free-text message - a conversation is made of these. */
export const AGENT_MESSAGE = "akgentic.agent.messages.AgentMessage";

/** The `__model__` tags this client reacts to, rather than merely displays. */
export const SLOT_QUESTION = "meeting_agents.messages.SlotApprovalRequest";
export const LUNCH_QUESTION = "meeting_agents.messages.LunchApprovalRequest";
export const PLAN_COMPLETED = "meeting_agents.messages.PlanCompleted";
export const PLAN_FAILED = "meeting_agents.messages.PlanFailed";
export const PLAN_CANCELLED = "meeting_agents.messages.PlanCancelled";

export interface ActorRef {
  name?: string;
  role?: string;
}

export interface DomainMessage {
  id: string;
  /**
   * The message this one answers. On a decision it is the question's `id`,
   * which is what lets a replayed trace say which gates are already closed
   * without the browser having to remember - see `TeamContext`.
   */
  parent_id?: string | null;
  __model__: string;
  [key: string]: unknown;
}

/**
 * A team run as the framework lists it.
 *
 * `status` is the one field worth distrusting. It means *alive*, not *busy*:
 * the framework idle-stops a team after `ORCHESTRATOR_TIMEOUT_DELAY` seconds
 * with nothing in flight (an hour by default), so a finished run reads
 * `running` until that fires. It is only meaningful next to a plan that has
 * not finished, where alive really does mean "still has work to do".
 */
export interface TeamSummary {
  team_id: string;
  name: string;
  status: "running" | "stopped" | string;
  created_at: string;
  /** What the run was asked to do (`MeetingTeamMetadata`), set when it was created. */
  metadata: { title?: string; day?: string; location_id?: string; participants?: number } | null;
  /** Which team card the run was made from - our namespace, or someone else's. */
  catalog_namespace: string | null;
}

export interface TeamEvent {
  id: string;
  __model__: string;
  timestamp: string;
  sender?: ActorRef | null;
  recipient?: ActorRef | null;
  /** Present on `SentMessage` only: the message that was actually sent. */
  message?: DomainMessage | null;
}

export interface ProposedSlot {
  start: string;
  end: string;
}

export interface SlotQuestion extends DomainMessage {
  plan_id: string;
  title: string;
  day: string;
  candidates: ProposedSlot[];
  /** The place, when the team chose it from a description - empty otherwise. */
  location_name: string;
  location_reason: string;
}

export interface LunchQuestion extends DomainMessage {
  plan_id: string;
  title: string;
  day: string;
  headcount: number;
}

export interface MeetingPlan {
  plan_id: string;
  title: string;
  participant_emails: string[];
  day: string;
  duration_minutes: number;
  location_id: string;
  location_wish: string;
  location_name: string;
  location_reason: string;
  with_lunch: boolean;
  lunch_wish: string;
  proposed_start: string | null;
  proposed_end: string | null;
  approved: boolean;
  meeting_id: number | null;
  room_code: string | null;
  booking_id: number | null;
  order_id: string | null;
  lunch_summary: string;
  cancelled: boolean;
  /** Derived on the server from which ids are present - never sent back. */
  status: string;
}

/**
 * The coordinator's state: the meeting's only record (design_durability.md R2).
 *
 * Read from the snapshot the framework persists, so it is there whether or
 * not the team is still running - which is what makes a list of teams as good
 * as the list of plans it replaced.
 */
export interface CoordinatorState {
  plan: MeetingPlan | null;
  candidates: ProposedSlot[];
  awaiting_lunch: boolean;
  failure: string;
  cancelling: unknown[];
  cancel_failures: string[];
}

/**
 * The next move is the human's: a gate is open (R6). The same rule as
 * `CoordinatorState.waiting_for_the_human` on the server - and deliberately
 * nothing about whether the team is alive, because a stopped team is revived
 * by the answer and its coordinator remembers what it asked.
 */
export function waitingForTheHuman(state: CoordinatorState): boolean {
  if (!state.plan || state.plan.cancelled || state.failure) return false;
  return state.candidates.length > 0 || state.awaiting_lunch;
}

export interface ServiceHealth {
  name: string;
  url: string;
  status: "up" | "degraded" | "unreachable";
  detail: string | null;
}

export interface PlatformHealth {
  status: "up" | "degraded";
  services: ServiceHealth[];
}

export interface PlanRequest {
  title: string;
  participant_emails: string[];
  day: string;
  duration_minutes: number;
  /** Exactly one of these two: a location id, or the place in your own words. */
  location_id: string;
  location_wish: string;
}

/**
 * What any run is about. A plan being cancelled describes its run the same way
 * the request that created it does, so a list of runs stays readable whichever
 * kind it is - and nothing has to be maintained, because both are facts that
 * were settled before the run started.
 */
export type RunSubject = Pick<
  MeetingPlan,
  "title" | "day" | "location_id" | "location_wish" | "participant_emails"
>;

/** Somebody who may log in: a person the meeting service knows. */
export interface Person {
  email: string;
  name: string;
}

/** Who the session says you are (`GET /auth/me`, design_auth.md A5). */
export interface Me {
  user_id: string;
  email: string;
  name: string;
  roles: string[];
}

/**
 * The principal of a server that has no login (`AUTH=off`): everybody is
 * `anonymous`, exactly as the framework's community tier has it.
 */
export const ANONYMOUS: Me = { user_id: "anonymous", email: "", name: "anonymous", roles: [] };

/**
 * Announced when the server says nobody is logged in.
 *
 * The session lives in an HttpOnly cookie no script can read, so the only way
 * to learn that it ended - expired, logged out in the console, the server
 * restarted without a secret - is a 401 from some call. Whoever holds the
 * session listens for this instead of every page handling it.
 */
export const UNAUTHORIZED = "meeting-planner:unauthorized";

function unauthorized(): void {
  window.dispatchEvent(new Event(UNAUTHORIZED));
}

/**
 * Every call carries the session cookie. The server is a second origin (G2),
 * and a cross-origin fetch sends no cookie unless asked to.
 */
async function send(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (response.status === 401) unauthorized();
  return response;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await send(path, init);
  if (!response.ok) {
    // The server's detail is the only useful part of a failure here - an
    // unreadable answer at a gate comes back this way, and the person who
    // typed it is the one who can fix it.
    const body = await response.text();
    throw new Error(body || `${response.status} ${response.statusText}`);
  }
  return response.status === 204 ? (null as T) : ((await response.json()) as T);
}

export const auth = {
  /**
   * Who is logged in: `null` when nobody is, `ANONYMOUS` when this server has
   * no login at all - a 404 on the route means the gate is off (`AUTH=off`).
   * Asked with a plain fetch, because "nobody" is an answer here, not a fault.
   */
  me: async (): Promise<Me | null> => {
    const response = await fetch(`${BASE}/auth/me`, { credentials: "include" });
    if (response.status === 404) return ANONYMOUS;
    if (!response.ok) return null;
    return (await response.json()) as Me;
  },

  people: () => call<Person[]>("/auth/users"),

  loginAs: async (email: string): Promise<Me> => {
    const body = await call<{ user: Me }>("/auth/login/person", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
    return body.user;
  },

  logout: () => call<{ success: boolean }>("/auth/logout"),
};

export const api = {
  platformHealth: () => call<PlatformHealth>("/platform/health"),

  /**
   * A team's meeting, read from its coordinator's persisted state.
   *
   * `null` for a team whose coordinator has no snapshot yet - created, but
   * never asked for anything - which the Meetings screen leaves out.
   */
  coordinatorState: async (teamId: string): Promise<CoordinatorState | null> => {
    const body = await call<{ states: { name: string | null; state: CoordinatorState }[] }>(
      `/teams/${teamId}/agent-states`,
    );
    return body.states.find((snapshot) => snapshot.name === COORDINATOR)?.state ?? null;
  },

  /**
   * The stored trace of a team that has already finished.
   *
   * The browser keeps the live stream in memory, but the events outlive it:
   * the server writes them per team and still serves them after the team has
   * stopped. The sequence wrapper is dropped here so a replayed trace and a
   * live one are the same shape to everything downstream.
   */
  teamEvents: async (teamId: string): Promise<TeamEvent[]> => {
    const body = await call<{ events: { event: TeamEvent }[] }>(
      `/teams/${teamId}/events`,
    );
    return body.events.map((entry) => entry.event);
  },

  /**
   * Create the team that will run one plan.
   *
   * The metadata is what makes a list of runs readable - in our Meetings screen,
   * and in the framework's own console, which renders whatever the team's
   * `metadata_type` declares. It is the request rather than the outcome, so it
   * can be set here, once, and never maintained (`team_metadata.py`).
   */
  createTeam: (subject: RunSubject) =>
    call<{ team_id: string }>("/teams", {
      method: "POST",
      body: JSON.stringify({
        catalog_namespace: TEAM_NAMESPACE,
        metadata: {
          title: subject.title,
          day: subject.day,
          // The request's "where", as it was asked: an id, or the words the
          // team will turn into one. It is known now and never maintained.
          location_id: subject.location_id || subject.location_wish,
          participants: subject.participant_emails.length,
        },
      }),
    }),

  /**
   * Start a plan. Not a conversation: the request is a typed message, so
   * nothing has to understand prose to get a meeting booked (design_gui.md
   * §4.1). The `__model__` tag names the class the server reconstructs.
   */
  startPlan: (teamId: string, request: PlanRequest) =>
    call<null>(`/teams/${teamId}/message/from/${HUMAN}/to/${COORDINATOR}`, {
      method: "POST",
      body: JSON.stringify({
        message: {
          __model__: "meeting_agents.messages.PlanMeetingRequest",
          ...request,
        },
      }),
    }),

  /**
   * Start a conversation: a chat team, with nothing asked yet.
   *
   * No metadata, unlike `createTeam`: nothing about the meeting is known
   * when a conversation starts, and the chat card declares no metadata type
   * (G18). The Meetings screen reads the title from the coordinator anyway.
   */
  createConversation: () =>
    call<{ team_id: string }>("/teams", {
      method: "POST",
      body: JSON.stringify({ catalog_namespace: CHAT_NAMESPACE }),
    }),

  /**
   * Say something to @Intake. Plain text: the framework wraps it in an
   * `AgentMessage` from @Human. A gate is never answered this way - only on
   * its card, through `answer` - which is what keeps "the human approves"
   * structural (design_chat.md I4).
   */
  say: (teamId: string, content: string) =>
    call<null>(`/teams/${teamId}/message/from/${HUMAN}/to/${INTAKE}`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),

  /** Answer a gate. `messageId` is the *inner* question id. */
  answer: (teamId: string, messageId: string, content: string) =>
    call<null>(`/teams/${teamId}/human-input`, {
      method: "POST",
      body: JSON.stringify({ content, message_id: messageId }),
    }),

  /**
   * Call a meeting off. Everything the plan booked is released.
   *
   * Sent to the team that made the meeting, because that team *is* the
   * meeting: its coordinator holds the only record of what was booked. A
   * stopped team is revived by the server to receive it (R4). There is no
   * update in this system, so this message carries no options - to change a
   * meeting you cancel it and plan another.
   */
  cancelPlan: (teamId: string, planId: string) =>
    call<null>(`/teams/${teamId}/message/from/${HUMAN}/to/${COORDINATOR}`, {
      method: "POST",
      body: JSON.stringify({
        message: {
          __model__: "meeting_agents.messages.CancelPlanRequest",
          plan_id: planId,
        },
      }),
    }),

  /** Every run the server knows about, newest state included. */
  listTeams: async (): Promise<TeamSummary[]> => {
    const body = await call<{ teams: TeamSummary[] }>("/teams");
    return body.teams;
  },

  /**
   * Bring a stopped team back before watching it.
   *
   * Delivering a message revives a stopped team on its own, and its
   * coordinator comes back knowing what it was waiting for - but a socket
   * opened on a stopped team only starts streaming when the team is restored
   * through *this* route, which is the one that wakes waiting sockets. So a
   * screen that wants to watch a stopped run asks for it here first. 409 means
   * it is already running, which is the outcome being asked for.
   */
  restoreTeam: async (teamId: string): Promise<void> => {
    const response = await send(`/teams/${teamId}/restore`, { method: "POST" });
    if (!response.ok && response.status !== 409) {
      throw new Error((await response.text()) || `${response.status} ${response.statusText}`);
    }
  },
};

/**
 * A socket closed for policy (1008) is the WebSocket's 401 - or its 404, for
 * a team that is not yours. Asking `/auth/me` tells the two apart, and
 * announces the first.
 */
export async function checkSession(): Promise<void> {
  if ((await auth.me()) === null) unauthorized();
}

export function streamUrl(teamId: string): string {
  return `${BASE.replace(/^http/, "ws")}/ws/${teamId}`;
}

/** The short class name, which is what a reader of the trace actually wants. */
export function shortName(model: string | undefined): string {
  return model ? model.split(".").pop()! : "";
}

/** Our messages, as opposed to the framework talking about itself. */
export function isDomainEvent(event: TeamEvent): boolean {
  return Boolean(event.message?.__model__?.startsWith("meeting_agents."));
}

/**
 * The part of an event worth reading.
 *
 * Every envelope carries the same six housekeeping fields; what differs is
 * where the content hides. `SentMessage` keeps it in `message`, `EventMessage`
 * in `event`, `StartMessage` in `config`, and `ReceivedMessage` /
 * `ProcessedMessage` carry nothing but a pointer back to the message they are
 * acknowledging.
 */
export function payloadOf(event: TeamEvent): Record<string, unknown> {
  const envelope = event as unknown as Record<string, unknown>;
  for (const key of ["message", "event", "config"]) {
    const value = envelope[key];
    if (value && typeof value === "object") {
      return value as Record<string, unknown>;
    }
  }
  return envelope.message_id ? { message_id: envelope.message_id } : {};
}

/** Fields that identify the envelope rather than say anything about the run. */
const PLUMBING = new Set([
  "id",
  "__model__",
  "parent_id",
  "team_id",
  "squad_id",
  "agent_id",
  "display_type",
]);

/**
 * The same data, minus the plumbing.
 *
 * An actor address is eleven fields of identity wrapped around one name. Left
 * alone it buries the payload it is attached to, so it collapses to the name -
 * which is what every other part of this screen shows anyway.
 */
export function readable(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(readable);
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    if (record.__actor_address__) return record.name ?? "";
    return Object.fromEntries(
      Object.entries(record)
        .filter(([key]) => !PLUMBING.has(key))
        .map(([key, nested]) => [key, readable(nested)]),
    );
  }
  return value;
}

/**
 * The payload, minus what is already on screen.
 *
 * An inner message repeats the envelope's own timestamp, sender and
 * recipient. Those are three columns of the grid and the dialog's own
 * subtitle, so repeating them in the content pushes the content out of view.
 * The raw tab still has everything.
 */
const ECHOED = new Set(["timestamp", "sender", "recipient", "parent", "parent_id"]);

export function contentOf(event: TeamEvent): Record<string, unknown> {
  const fields = readable(payloadOf(event)) as Record<string, unknown>;
  return Object.fromEntries(Object.entries(fields).filter(([key]) => !ECHOED.has(key)));
}

/** One line of content for the grid: enough to recognise, never enough to read. */
export function summarise(event: TeamEvent): string {
  const parts = Object.entries(contentOf(event))
    .filter(([, value]) => value !== null && value !== "" && value !== undefined)
    .map(([key, value]) => `${key}: ${scalar(value)}`);
  const line = parts.join(", ");
  return line.length > 120 ? `${line.slice(0, 119)}…` : line;
}

function scalar(value: unknown): string {
  if (Array.isArray(value)) {
    return value.length <= 2 ? value.map(scalar).join(" / ") : `${value.length} items`;
  }
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    const named = shortName(record.__model__ as string | undefined);
    // A nested object with no class name of its own still has fields; the
    // first couple of them say more than "{…}" ever does.
    const peek = Object.entries(record)
      .filter(([key, nested]) => !ECHOED.has(key) && nested !== null && typeof nested !== "object")
      .slice(0, 2)
      .map(([key, nested]) => `${key}: ${String(nested)}`)
      .join(", ");
    if (peek) return named ? `${named}(${peek})` : `{${peek}}`;
    return named || "{…}";
  }
  return String(value);
}

