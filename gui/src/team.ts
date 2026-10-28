import { createContext, useContext } from "react";
import type { DomainMessage, PlanRequest, TeamEvent } from "./api/client";

/**
 * One plan's worth of state, shared by the screens that watch it.
 *
 * The stream lives here rather than in a page because there must be exactly
 * one socket: the server replays from cursor zero on connect, so a second
 * subscriber is a second full replay, and a page that mounts late would
 * otherwise start the story again from the beginning.
 */
export interface TeamState {
  teamId: string | null;
  /** Which kind of team is being watched: the form's, or the conversation's. */
  namespace: string | null;
  events: TeamEvent[];
  connected: boolean;
  starting: boolean;
  error: string | null;
  /** The question the team is waiting on, or null if it is working. */
  pending: DomainMessage | null;
  /** `PlanCompleted` or `PlanFailed`, once one has arrived. */
  outcome: DomainMessage | null;
  start: (request: PlanRequest) => Promise<void>;
  /**
   * Watch a run that is already going, instead of starting one.
   *
   * Everything below is derived from the stream, and the server replays a
   * team's whole history on connect, so attaching needs nothing but the id:
   * the questions, the answers already given and the outcome all arrive again
   * and the screen rebuilds itself.
   */
  attach: (teamId: string, namespace?: string) => void;
  answer: (content: string) => Promise<void>;
  /**
   * Say something in a conversation, starting one first if the team being
   * watched is not a conversation. Free text to @Intake; never a gate answer.
   */
  say: (content: string) => Promise<void>;
  reset: () => void;
}

export const Context = createContext<TeamState | null>(null);

export function useTeam(): TeamState {
  const value = useContext(Context);
  if (!value) throw new Error("useTeam must be used inside a TeamProvider");
  return value;
}
