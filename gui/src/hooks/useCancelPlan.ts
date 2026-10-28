import { useCallback, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  api,
  isDomainEvent,
  PLAN_CANCELLED,
  type DomainMessage,
  type MeetingPlan,
} from "../api/client";
import { useTeamStream } from "./useTeamStream";

/**
 * Calling a meeting off, as a run the browser can watch.
 *
 * A cancellation is a team run like any other - it has a trace, it appears in
 * the console, and it is added to the plan's list of runs by the repository
 * that stores the result. So it is driven the same way a plan is: create a
 * team, send one typed message, and read the answer off the stream.
 *
 * It asks no questions, which is the whole difference. There is no gate to
 * answer, because there is nothing left to decide once the human has said yes.
 *
 * ## Any live run is stopped first, and that is not politeness
 *
 * `PlanStore.save` is a blind replace - last write wins, no version check -
 * and a cancellation runs in a *second* team while the first may still be
 * holding the plan in memory. Release the room, and a team that is still
 * going books the lunch and saves its own copy over the top: the plan reads
 * CONFIRMED again, with a meeting that no longer exists and an order nothing
 * references. Stopping is synchronous, so once it returns the old team cannot
 * write at all. That is what makes this safe rather than merely likely.
 */
export function useCancelPlan() {
  const [teamId, setTeamId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { events } = useTeamStream(teamId);
  const queryClient = useQueryClient();

  const outcome = useMemo<DomainMessage | null>(
    () =>
      events
        .filter(isDomainEvent)
        .map((event) => event.message!)
        .find((message) => message.__model__ === PLAN_CANCELLED) ?? null,
    [events],
  );

  // The grid is reading the store, and the store has only now changed. The
  // agents report a cancellation after the write, so by the time this fires
  // there is a cancelled plan to re-read.
  useEffect(() => {
    if (outcome) {
      void queryClient.invalidateQueries({ queryKey: ["plans"] });
      void queryClient.invalidateQueries({ queryKey: ["teams"] });
    }
  }, [outcome, queryClient]);

  const run = useCallback(async (plan: MeetingPlan) => {
    setStarting(true);
    setError(null);
    setTeamId(null);
    try {
      // Every run that touched this plan, not just the one that looked alive
      // a moment ago: liveness is polled, and stopping something already
      // stopped is free.
      for (const previous of plan.team_ids) {
        await api.stopTeam(previous);
      }
      const team = await api.createTeam(plan);
      setTeamId(team.team_id);
      await api.cancelPlan(team.team_id, plan.plan_id);
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : String(problem));
    } finally {
      setStarting(false);
    }
  }, []);

  const reset = useCallback(() => {
    setTeamId(null);
    setError(null);
  }, []);

  return {
    teamId,
    error,
    outcome,
    /** True from the moment it is asked for until the answer arrives. */
    running: (starting || Boolean(teamId)) && !outcome && !error,
    run,
    reset,
  };
}
