import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  FormControlLabel,
  LinearProgress,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useState } from "react";
import {
  CHAT_NAMESPACE,
  isDomainEvent,
  PLAN_COMPLETED,
  shortName,
  type MeetingPlan,
} from "../api/client";
import { GatePrompt } from "../components/GatePrompt";
import { useSession } from "../session";
import { useTeam } from "../team";

const TODAY_PLUS_A_YEAR = new Date(Date.now() + 365 * 24 * 3600 * 1000)
  .toISOString()
  .slice(0, 10);

export default function PlanPage() {
  const team = useTeam();
  const [title, setTitle] = useState("Design review");
  const [people, setPeople] = useState("sanne@rag4p.org, daan@rag4p.org");
  const [day, setDay] = useState(TODAY_PLUS_A_YEAR);
  const [duration, setDuration] = useState(60);
  const [location, setLocation] = useState("yuma");
  // A place can be named by id or described in words; the team chooses from
  // a description (design_chat.md §13.1). One field at a time, so the request
  // always carries exactly one of the two.
  const [describe, setDescribe] = useState(false);
  const [placeWish, setPlaceWish] = useState("somewhere in nature");
  // You attend your own meeting unless you say otherwise (design_auth.md A18).
  // Without a login there is no organiser, so there is nothing to ask.
  const { user } = useSession();
  const organiser = user && user.user_id !== "anonymous" ? user : null;
  const [attend, setAttend] = useState(true);

  const submit = () =>
    team.start({
      title,
      participant_emails: people
        .split(",")
        .map((email) => email.trim())
        .filter(Boolean),
      day,
      duration_minutes: duration,
      location_id: describe ? "" : location,
      location_wish: describe ? placeWish : "",
      organiser_attends: attend,
    });

  const plan = team.outcome?.plan as MeetingPlan | undefined;
  const succeeded = team.outcome?.__model__ === PLAN_COMPLETED;
  // The provider holds one team at a time; a conversation belongs on its own
  // page, so here it reads as "nothing planned from the form yet".
  const watching = team.teamId !== null && team.namespace !== CHAT_NAMESPACE;
  const working = watching && !team.pending && !team.outcome;

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Plan a meeting
      </Typography>

      {!watching && (
        <Card variant="outlined">
          <CardContent>
            <Stack spacing={2}>
              <TextField
                label="Title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
              />
              <TextField
                label="Participants"
                helperText={
                  organiser ? "The others, as email addresses, comma separated" : "Email addresses, comma separated"
                }
                value={people}
                onChange={(event) => setPeople(event.target.value)}
              />
              {organiser && (
                <FormControlLabel
                  control={<Checkbox checked={attend} onChange={(event) => setAttend(event.target.checked)} />}
                  label={`I attend (${organiser.name})`}
                />
              )}
              <Stack direction="row" spacing={2}>
                <TextField
                  label="Day"
                  type="date"
                  value={day}
                  onChange={(event) => setDay(event.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
                <TextField
                  label="Minutes"
                  type="number"
                  value={duration}
                  onChange={(event) => setDuration(Number(event.target.value))}
                />
                {describe ? (
                  <TextField
                    label="Describe the place"
                    helperText="The team chooses a location that fits"
                    value={placeWish}
                    onChange={(event) => setPlaceWish(event.target.value)}
                    sx={{ flexGrow: 1 }}
                  />
                ) : (
                  <TextField
                    label="Location"
                    value={location}
                    onChange={(event) => setLocation(event.target.value)}
                  />
                )}
              </Stack>
              <Box>
                <Button size="small" onClick={() => setDescribe(!describe)}>
                  {describe ? "Name a location instead" : "Describe the place instead"}
                </Button>
              </Box>
              <Box>
                <Button variant="contained" onClick={submit} disabled={team.starting}>
                  Ask the team
                </Button>
              </Box>
            </Stack>
          </CardContent>
        </Card>
      )}

      {team.error && (
        <Alert severity="warning" sx={{ mt: 2 }}>
          {team.error}
        </Alert>
      )}

      {watching && (
        <Stack spacing={2} sx={{ mt: 2 }}>
          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            <Chip
              size="small"
              color={team.connected ? "success" : "default"}
              label={team.connected ? "watching" : "connecting"}
            />
            <Typography variant="body2" color="text.secondary">
              team {team.teamId}
            </Typography>
          </Stack>

          {working && (
            <Card variant="outlined">
              <CardContent>
                <Typography gutterBottom>{lastStep(team.events)}</Typography>
                <LinearProgress />
              </CardContent>
            </Card>
          )}

          {team.pending && (
            <GatePrompt question={team.pending} onAnswer={team.answer} />
          )}

          {team.outcome && (
            <Alert severity={succeeded ? "success" : "error"}>
              {succeeded ? "Booked." : String(team.outcome.reason ?? "The plan failed.")}
            </Alert>
          )}

          {plan && succeeded && <PlanSummary plan={plan} />}

          <Box>
            <Button onClick={team.reset}>Plan another</Button>
          </Box>
        </Stack>
      )}
    </Box>
  );
}

/** What the team is doing right now, in the team's own vocabulary. */
function lastStep(events: ReturnType<typeof useTeam>["events"]): string {
  const domain = events.filter(isDomainEvent);
  const latest = domain[domain.length - 1];
  if (!latest) return "Starting the team…";
  const from = latest.sender?.name ?? "";
  const to = latest.recipient?.name ?? "";
  return `${from} → ${to}: ${shortName(latest.message?.__model__)}`;
}

export function PlanSummary({ plan }: { plan: MeetingPlan }) {
  const rows: [string, string][] = [
    ["When", `${plan.day} ${plan.proposed_start?.slice(0, 5)}–${plan.proposed_end?.slice(0, 5)}`],
    ["Who", plan.participant_emails.join(", ")],
    ["Room", `${plan.room_code ?? "—"} at ${plan.location_name || plan.location_id}`],
    ["Lunch", plan.lunch_summary || "none"],
  ];

  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {plan.title}
        </Typography>
        <Stack spacing={1}>
          {rows.map(([label, value]) => (
            <Stack direction="row" spacing={2} key={label}>
              <Typography variant="body2" color="text.secondary" sx={{ width: 80 }}>
                {label}
              </Typography>
              <Typography variant="body2">{value}</Typography>
            </Stack>
          ))}
        </Stack>
      </CardContent>
    </Card>
  );
}
