import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AGENT_MESSAGE,
  CHAT_NAMESPACE,
  HUMAN,
  INTAKE,
  PLAN_CANCELLED,
  PLAN_COMPLETED,
  type MeetingPlan,
  type TeamEvent,
} from "../api/client";
import { GatePrompt } from "../components/GatePrompt";
import { useTeam } from "../TeamContext";
import { PlanSummary } from "./PlanPage";

/** One line of the conversation, as it was said. */
interface Line {
  id: string;
  from: "you" | "planner";
  text: string;
}

/**
 * The free-text lines between the human and @Intake, in order.
 *
 * Everything else in the trace - the coordinator's typed traffic, the relayed
 * questions - is shown as cards or not at all. A notification @Intake chose to
 * answer with nothing simply is not a line.
 */
function conversation(events: TeamEvent[]): Line[] {
  return events.flatMap((event): Line[] => {
    const message = event.message;
    if (message?.__model__ !== AGENT_MESSAGE) return [];
    const from = event.sender?.name;
    const to = event.recipient?.name;
    const text = String(message.content ?? "").trim();
    if (!text) return [];
    if (from === HUMAN && to === INTAKE) return [{ id: event.id, from: "you", text }];
    if (from === INTAKE && to === HUMAN) return [{ id: event.id, from: "planner", text }];
    return [];
  });
}

/**
 * Talk to the planner (design_chat.md §9).
 *
 * The conversation is with @Intake, which turns it into the same typed request
 * the form sends; the deterministic team behind it books, as always. Two
 * channels share the page and are kept apart on purpose:
 *
 * - **the input box always talks to @Intake** - free text, a new message;
 * - **a gate is answered on its card**, through /human-input, exactly as on the
 *   plan page. Nothing typed into the conversation can approve a time, which is
 *   what keeps "the human approves" structural (I4).
 */
export default function ChatPage() {
  const team = useTeam();
  const navigate = useNavigate();
  const [draft, setDraft] = useState("");

  // The provider holds one team; only a conversation is shown here.
  const mine = team.teamId !== null && team.namespace === CHAT_NAMESPACE;
  const lines = useMemo(() => (mine ? conversation(team.events) : []), [mine, team.events]);
  const plan = team.outcome?.plan as MeetingPlan | undefined;
  const booked = team.outcome?.__model__ === PLAN_COMPLETED;
  const cancelled = mine && team.events.some(
    (event) => event.recipient?.name === HUMAN && event.message?.__model__ === PLAN_CANCELLED,
  );
  // Waiting for the planner: the last thing said was yours.
  const thinking = team.starting || (mine && lines.length > 0 && lines[lines.length - 1].from === "you");

  const send = async () => {
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    await team.say(text);
  };

  return (
    <Box>
      <Stack direction="row" spacing={2} sx={{ alignItems: "center", mb: 2 }}>
        <Typography variant="h5" sx={{ flexGrow: 1 }}>
          Talk to the planner
        </Typography>
        {mine && (
          <>
            <Button size="small" onClick={() => navigate(`/trace/${team.teamId}`)}>
              Open the trace
            </Button>
            <Button size="small" variant="outlined" onClick={() => team.reset()}>
              New conversation
            </Button>
          </>
        )}
      </Stack>

      <Card variant="outlined">
        <CardContent>
          <Stack spacing={1.5}>
            {lines.length === 0 && (
              <Typography color="text.secondary">
                Say what meeting you would like — who, which day, and what kind of place. Names
                and descriptions are fine: the team looks people up and chooses a place that fits,
                and you approve the time and place before anything is booked.
              </Typography>
            )}

            {lines.map((line) => (
              <Bubble key={line.id} line={line} />
            ))}

            {thinking && (
              <Stack direction="row" spacing={1} sx={{ alignItems: "center", color: "text.secondary" }}>
                <CircularProgress size={14} />
                <Typography variant="body2">The planner is thinking…</Typography>
              </Stack>
            )}

            {mine && team.pending && <GatePrompt question={team.pending} onAnswer={team.answer} />}

            {mine && booked && plan && <PlanSummary plan={plan} />}
            {mine && team.outcome && !booked && (
              <Alert severity="error">{String(team.outcome.reason ?? "The meeting could not be arranged.")}</Alert>
            )}
            {cancelled && <Chip color="error" label="cancelled — everything was released" sx={{ alignSelf: "flex-start" }} />}
          </Stack>
        </CardContent>
      </Card>

      {team.error && (
        <Alert severity="warning" sx={{ mt: 2 }}>
          {team.error}
        </Alert>
      )}

      <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
        <TextField
          fullWidth
          size="small"
          placeholder={mine ? "Say something to the planner" : "e.g. A design review with Sanne and Daan next Tuesday, somewhere quiet"}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void send();
            }
          }}
          disabled={team.starting}
        />
        <Button variant="contained" onClick={() => void send()} disabled={team.starting || !draft.trim()}>
          Send
        </Button>
      </Stack>
    </Box>
  );
}

function Bubble({ line }: { line: Line }) {
  const yours = line.from === "you";
  return (
    <Box sx={{ display: "flex", justifyContent: yours ? "flex-end" : "flex-start" }}>
      <Box
        sx={{
          maxWidth: "75%",
          px: 1.5,
          py: 1,
          borderRadius: 2,
          bgcolor: yours ? "primary.main" : "grey.100",
          color: yours ? "primary.contrastText" : "text.primary",
          whiteSpace: "pre-wrap",
        }}
      >
        <Typography variant="body2">{line.text}</Typography>
      </Box>
    </Box>
  );
}
