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
 * Calling a meeting off, watched on the stream of the team that made it.
 *
 * The cancellation goes to the meeting's own team (design_durability.md R4):
 * its coordinator holds the only record of what was booked, so nothing has to
 * be loaded and no second team is created. The server revives the team if it
 * has stopped. The booking and its undoing end up in one trace.
 *
 * There is nothing to stop first, either. The old design stopped every live
 * run before cancelling because two teams could write the same plan; now one
 * team owns it, and a booking still in flight when the cancel arrives is
 * released by the coordinator when it lands (R5).
 *
 * It asks no questions. There is no gate to answer, because there is nothing
 * left to decide once the human has said yes.
 */
export function useCancelPlan() {
  const [teamId, setTeamId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { events } = useTeamStream(teamId);
  const queryClient = useQueryClient();

  // The stream replays the team's whole history, but a meeting is cancelled
  // once - the button goes once it is - so the first report on it is the
  // answer. A booking released late (R5) reports again, after it.
  const outcome = useMemo<DomainMessage | null>(
    () =>
      events
        .filter(isDomainEvent)
        .map((event) => event.message!)
        .find((message) => message.__model__ === PLAN_CANCELLED) ?? null,
    [events],
  );

  // The coordinator reports after its state records the cancellation (R8), so
  // by the time this fires there is a cancelled meeting to re-read.
  useEffect(() => {
    if (outcome) {
      void queryClient.invalidateQueries({ queryKey: ["teams"] });
      void queryClient.invalidateQueries({ queryKey: ["coordinator"] });
    }
  }, [outcome, queryClient]);

  const run = useCallback(async (meetingTeamId: string, plan: MeetingPlan) => {
    setStarting(true);
    setError(null);
    try {
      // Restored before the socket opens: a socket on a stopped team waits
      // for a restore, and the cancel alone would revive the team without
      // waking it. The stream replays from the start, so nothing is missed.
      await api.restoreTeam(meetingTeamId);
      setTeamId(meetingTeamId);
      await api.cancelPlan(meetingTeamId, plan.plan_id);
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
