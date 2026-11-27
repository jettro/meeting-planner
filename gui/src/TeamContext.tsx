import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  api,
  CHAT_NAMESPACE,
  HUMAN,
  isDomainEvent,
  LUNCH_QUESTION,
  MOVE_FAILED,
  PLAN_COMPLETED,
  PLAN_FAILED,
  PLAN_MOVED,
  SLOT_QUESTION,
  TEAM_NAMESPACE,
  type DomainMessage,
  type PlanRequest,
  type TeamEvent,
} from "./api/client";
import { useTeamStream } from "./hooks/useTeamStream";
import { Context, type TeamState } from "./team";


const QUESTIONS = new Set([SLOT_QUESTION, LUNCH_QUESTION]);
const OUTCOMES = new Set([PLAN_COMPLETED, PLAN_FAILED, PLAN_MOVED, MOVE_FAILED]);
const QUESTIONS_AND_OUTCOMES = new Set([...QUESTIONS, ...OUTCOMES]);

/**
 * Questions and outcomes addressed to the human (design_chat.md I9).
 *
 * In a conversation every question is in the trace twice: the coordinator's
 * copy to @Intake, and the relay's fresh copy to @Human. Only the second is the
 * human's - it is the one /human-input can route - so only messages addressed
 * to @Human count. In the form team every question already is, so nothing
 * changes there.
 */
function messagesOfKind(events: TeamEvent[], kinds: Set<string>): DomainMessage[] {
  return events
    .filter(isDomainEvent)
    .filter((event) => event.recipient?.name === HUMAN)
    .map((event) => event.message!)
    .filter((message) => kinds.has(message.__model__));
}

export function TeamProvider({ children }: { children: ReactNode }) {
  const [teamId, setTeamId] = useState<string | null>(null);
  const [namespace, setNamespace] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answered, setAnswered] = useState<string[]>([]);
  const { events, status } = useTeamStream(teamId);
  // The id of the question being answered, read at submit time rather than
  // from a closure, so an answer cannot be attached to a stale question.
  const pendingRef = useRef<DomainMessage | null>(null);

  // In the order they arrived. A meeting can have more than one outcome: it is
  // booked, then moved (design_move.md M13), so the latest one is what holds,
  // and only a question asked after it can still be open.
  const toTheHuman = useMemo(() => messagesOfKind(events, QUESTIONS_AND_OUTCOMES), [events]);
  const lastOutcome = toTheHuman.map((message) => OUTCOMES.has(message.__model__)).lastIndexOf(true);
  const outcome = lastOutcome >= 0 ? toTheHuman[lastOutcome] : null;

  const pending = useMemo(() => {
    // A question is closed when its answer is in the stream - every decision
    // carries the question's id as its `parent_id`. Reading it from the
    // events rather than from what this browser happens to have typed is what
    // makes a resumed run correct: the answers given before the tab was
    // closed are in the replay, so the gate that is genuinely still open is
    // the one that shows.
    const closed = new Set(
      events
        .filter(isDomainEvent)
        .map((event) => event.message!.parent_id)
        .filter((id): id is string => Boolean(id)),
    );
    const open = toTheHuman
      .slice(lastOutcome + 1)
      .filter((message) => QUESTIONS.has(message.__model__))
      .filter((question) => !closed.has(question.id) && !answered.includes(question.id));
    return open[open.length - 1] ?? null;
  }, [events, toTheHuman, lastOutcome, answered]);

  useEffect(() => {
    pendingRef.current = pending;
  }, [pending]);

  const start = useCallback(async (request: PlanRequest) => {
    setStarting(true);
    setError(null);
    setAnswered([]);
    try {
      const team = await api.createTeam(request);
      // The team exists before the plan is sent, so a failure here still
      // leaves something to look at in the trace.
      setTeamId(team.team_id);
      setNamespace(TEAM_NAMESPACE);
      await api.startPlan(team.team_id, request);
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : String(problem));
    } finally {
      setStarting(false);
    }
  }, []);

  const attach = useCallback((existingTeamId: string, existingNamespace: string = TEAM_NAMESPACE) => {
    setError(null);
    setAnswered([]);
    setTeamId(existingTeamId);
    setNamespace(existingNamespace);
  }, []);

  const say = useCallback(
    async (content: string) => {
      setError(null);
      try {
        let conversation = namespace === CHAT_NAMESPACE ? teamId : null;
        if (!conversation) {
          setStarting(true);
          setAnswered([]);
          conversation = (await api.createConversation()).team_id;
          setTeamId(conversation);
          setNamespace(CHAT_NAMESPACE);
        }
        await api.say(conversation, content);
      } catch (problem) {
        setError(problem instanceof Error ? problem.message : String(problem));
      } finally {
        setStarting(false);
      }
    },
    [namespace, teamId],
  );

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
    setNamespace(null);
    setAnswered([]);
    setError(null);
  }, []);

  const value: TeamState = {
    teamId,
    namespace,
    events,
    connected: status === "open",
    starting,
    error,
    pending,
    outcome,
    start,
    attach,
    answer,
    say,
    reset,
  };

  return <Context.Provider value={value}>{children}</Context.Provider>;
}
