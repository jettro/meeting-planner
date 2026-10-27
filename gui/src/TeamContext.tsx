import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  api,
  isDomainEvent,
  LUNCH_QUESTION,
  PLAN_COMPLETED,
  PLAN_FAILED,
  SLOT_QUESTION,
  type DomainMessage,
  type PlanRequest,
  type TeamEvent,
} from "./api/client";
import { useTeamStream } from "./hooks/useTeamStream";

/**
 * One plan's worth of state, shared by the screens that watch it.
 *
 * The stream lives here rather than in a page because there must be exactly
 * one socket: the server replays from cursor zero on connect, so a second
 * subscriber is a second full replay, and a page that mounts late would
 * otherwise start the story again from the beginning.
 */
interface TeamState {
  teamId: string | null;
  events: TeamEvent[];
  connected: boolean;
  starting: boolean;
  error: string | null;
  /** The question the team is waiting on, or null if it is working. */
  pending: DomainMessage | null;
  /** `PlanCompleted` or `PlanFailed`, once one has arrived. */
  outcome: DomainMessage | null;
  start: (request: PlanRequest) => Promise<void>;
  answer: (content: string) => Promise<void>;
  reset: () => void;
}

const Context = createContext<TeamState | null>(null);

const QUESTIONS = new Set([SLOT_QUESTION, LUNCH_QUESTION]);
const OUTCOMES = new Set([PLAN_COMPLETED, PLAN_FAILED]);

function messagesOfKind(events: TeamEvent[], kinds: Set<string>): DomainMessage[] {
  return events
    .filter(isDomainEvent)
    .map((event) => event.message!)
    .filter((message) => kinds.has(message.__model__));
}

export function TeamProvider({ children }: { children: ReactNode }) {
  const [teamId, setTeamId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answered, setAnswered] = useState<string[]>([]);
  const { events, status } = useTeamStream(teamId);
  // The id of the question being answered, read at submit time rather than
  // from a closure, so an answer cannot be attached to a stale question.
  const pendingRef = useRef<DomainMessage | null>(null);

  const outcome = useMemo(
    () => messagesOfKind(events, OUTCOMES)[0] ?? null,
    [events],
  );

  const pending = useMemo(() => {
    if (outcome) return null;
    const open = messagesOfKind(events, QUESTIONS).filter(
      (question) => !answered.includes(question.id),
    );
    return open[open.length - 1] ?? null;
  }, [events, answered, outcome]);

  useEffect(() => {
    pendingRef.current = pending;
  }, [pending]);

  const start = useCallback(async (request: PlanRequest) => {
    setStarting(true);
    setError(null);
    setAnswered([]);
    try {
      const team = await api.createTeam();
      // The team exists before the plan is sent, so a failure here still
      // leaves something to look at in the trace.
      setTeamId(team.team_id);
      await api.startPlan(team.team_id, request);
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : String(problem));
    } finally {
      setStarting(false);
    }
  }, []);

  const answer = useCallback(
    async (content: string) => {
      const question = pendingRef.current;
      if (!teamId || !question) return;
      setError(null);
      try {
        await api.answer(teamId, question.id, content);
        setAnswered((previous) => [...previous, question.id]);
      } catch (problem) {
        // An answer the server could not read comes back here. The question
        // stays open on purpose, so it can simply be answered again.
        setError(problem instanceof Error ? problem.message : String(problem));
      }
    },
    [teamId],
  );

  const reset = useCallback(() => {
    setTeamId(null);
    setAnswered([]);
    setError(null);
  }, []);

  const value: TeamState = {
    teamId,
    events,
    connected: status === "open",
    starting,
    error,
    pending,
    outcome,
    start,
    answer,
    reset,
  };

  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useTeam(): TeamState {
  const value = useContext(Context);
  if (!value) throw new Error("useTeam must be used inside a TeamProvider");
  return value;
}
