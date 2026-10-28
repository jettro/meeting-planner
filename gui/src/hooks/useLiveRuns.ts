import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

/**
 * Which team runs are still alive.
 *
 * This is what tells an unfinished plan apart from an abandoned one. The
 * coordinator keeps its state in memory and is not durable, so a stopped team
 * can never be continued - whatever it was in the middle of is gone, and the
 * only thing left to do with its plan is release what it managed to book.
 * While the team is alive the opposite is true: it is almost certainly parked
 * at a gate, waiting for an answer it will still accept.
 *
 * The framework idle-stops a team an hour after its last message, so this
 * goes stale on its own. It is polled rather than cached indefinitely, and
 * every action taken on the back of it tolerates being wrong by the time it
 * is used.
 */
export function useLiveRuns() {
  const { data } = useQuery({
    queryKey: ["teams"],
    queryFn: api.listTeams,
    refetchInterval: 30_000,
  });

  const running = new Set(
    (data ?? []).filter((team) => team.status === "running").map((team) => team.team_id),
  );

  /** The live run for a plan, or null if nothing is still working on it. */
  return (teamIds: string[]): string | null =>
    teamIds.find((teamId) => running.has(teamId)) ?? null;
}
