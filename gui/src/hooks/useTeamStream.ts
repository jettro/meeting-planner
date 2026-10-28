import { useEffect, useRef, useState } from "react";
import { streamUrl, type TeamEvent } from "../api/client";

export type StreamStatus = "idle" | "connecting" | "open" | "closed";

/** What one socket has delivered, tagged with the team it belongs to. */
interface Stream {
  teamId: string | null;
  events: TeamEvent[];
  status: StreamStatus;
}

/**
 * The team's events, live.
 *
 * Two details carry the whole hook. The server replays **from cursor zero on
 * every connect**, so a reconnect re-sends everything the client has already
 * seen - which is why ids are tracked and duplicates dropped rather than
 * appended. And the browser keeps the events in state rather than refetching,
 * because the trace is the one screen where losing the middle of the story
 * defeats the point.
 *
 * The state is tagged with the team it was collected for, so switching teams
 * needs no reset: a stream for another team simply reads as empty and
 * connecting until this one's socket says otherwise. The effect only ever sets
 * state from the socket's own callbacks - it synchronises with the socket and
 * nothing else.
 */
export function useTeamStream(teamId: string | null) {
  const [stream, setStream] = useState<Stream>({ teamId: null, events: [], status: "idle" });
  const seen = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!teamId) return;
    seen.current = new Set();

    const update = (change: (current: Stream) => Partial<Stream>) =>
      setStream((current) => {
        const mine = current.teamId === teamId ? current : { teamId, events: [], status: "connecting" as const };
        return { ...mine, ...change(mine) };
      });

    const socket = new WebSocket(streamUrl(teamId));
    socket.onopen = () => update(() => ({ status: "open" }));
    socket.onclose = () => update(() => ({ status: "closed" }));
    socket.onerror = () => update(() => ({ status: "closed" }));
    socket.onmessage = (frame) => {
      const event = JSON.parse(frame.data) as TeamEvent;
      if (seen.current.has(event.id)) return;
      seen.current.add(event.id);
      update((current) => ({ events: [...current.events, event] }));
    };

    return () => {
      socket.close();
      // Forget what this socket delivered. Coming back to the same team later
      // opens a new socket, and the server replays everything from cursor
      // zero - keeping these would show the story twice.
      setStream({ teamId: null, events: [], status: "idle" });
    };
  }, [teamId]);

  if (!teamId) return { events: [] as TeamEvent[], status: "idle" as StreamStatus };
  if (stream.teamId !== teamId) return { events: [] as TeamEvent[], status: "connecting" as StreamStatus };
  return { events: stream.events, status: stream.status };
}
