import { useEffect, useRef, useState } from "react";
import { streamUrl, type TeamEvent } from "../api/client";

export type StreamStatus = "idle" | "connecting" | "open" | "closed";

/**
 * The team's events, live.
 *
 * Two details carry the whole hook. The server replays **from cursor zero on
 * every connect**, so a reconnect re-sends everything the client has already
 * seen - which is why ids are tracked and duplicates dropped rather than
 * appended. And the browser keeps the events in state rather than refetching,
 * because the trace is the one screen where losing the middle of the story
 * defeats the point.
 */
export function useTeamStream(teamId: string | null) {
  const [events, setEvents] = useState<TeamEvent[]>([]);
  const [status, setStatus] = useState<StreamStatus>("idle");
  const seen = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!teamId) {
      setEvents([]);
      seen.current = new Set();
      setStatus("idle");
      return;
    }

    seen.current = new Set();
    setEvents([]);
    setStatus("connecting");

    const socket = new WebSocket(streamUrl(teamId));
    socket.onopen = () => setStatus("open");
    socket.onclose = () => setStatus("closed");
    socket.onerror = () => setStatus("closed");
    socket.onmessage = (frame) => {
      const event = JSON.parse(frame.data) as TeamEvent;
      if (seen.current.has(event.id)) return;
      seen.current.add(event.id);
      setEvents((previous) => [...previous, event]);
    };

    return () => socket.close();
  }, [teamId]);

  return { events, status };
}
