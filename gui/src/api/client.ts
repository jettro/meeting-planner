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
export const HUMAN = "@Human";
export const COORDINATOR = "@Coordinator";

/** The `__model__` tags this client reacts to, rather than merely displays. */
export const SLOT_QUESTION = "meeting_agents.messages.SlotApprovalRequest";
export const LUNCH_QUESTION = "meeting_agents.messages.LunchApprovalRequest";
export const PLAN_COMPLETED = "meeting_agents.messages.PlanCompleted";
export const PLAN_FAILED = "meeting_agents.messages.PlanFailed";

export interface ActorRef {
  name?: string;
  role?: string;
}

export interface DomainMessage {
  id: string;
  __model__: string;
  [key: string]: unknown;
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
  location_id: string;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    // The server's detail is the only useful part of a failure here - an
    // unreadable answer at a gate comes back this way, and the person who
    // typed it is the one who can fix it.
    const body = await response.text();
    throw new Error(body || `${response.status} ${response.statusText}`);
  }
  return response.status === 204 ? (null as T) : ((await response.json()) as T);
}

export const api = {
  platformHealth: () => call<PlatformHealth>("/platform/health"),

  plans: () => call<MeetingPlan[]>("/plans"),

  createTeam: () =>
    call<{ team_id: string }>("/teams", {
      method: "POST",
      body: JSON.stringify({ catalog_namespace: TEAM_NAMESPACE }),
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

  /** Answer a gate. `messageId` is the *inner* question id. */
  answer: (teamId: string, messageId: string, content: string) =>
    call<null>(`/teams/${teamId}/human-input`, {
      method: "POST",
      body: JSON.stringify({ content, message_id: messageId }),
    }),

  stopTeam: (teamId: string) =>
    call<null>(`/teams/${teamId}`, { method: "DELETE" }),
};

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

