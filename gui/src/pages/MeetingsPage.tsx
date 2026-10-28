import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  LinearProgress,
  Stack,
  Typography,
} from "@mui/material";
import { DataGrid, type GridColDef } from "@mui/x-data-grid";
import { useQueries, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  api,
  TEAM_NAMESPACE,
  waitingForTheHuman,
  type CoordinatorState,
  type MeetingPlan,
} from "../api/client";
import { useCancelPlan } from "../hooks/useCancelPlan";
import { useTeam } from "../TeamContext";

/** One team run, and the meeting it arranged. One team is one meeting. */
interface Meeting {
  teamId: string;
  createdAt: string;
  state: CoordinatorState;
  plan: MeetingPlan;
}

/**
 * Every meeting the team has arranged, including the ones nobody is watching.
 *
 * There is no plan store behind this (design_durability.md R3, R7). One team
 * arranges one meeting, and its coordinator's state is the only record of it,
 * so the list of meetings is the list of teams: `GET /teams` for the runs, and
 * each run's coordinator snapshot for what came of it. The framework persists
 * that snapshot and serves it after the team has stopped, which is what makes
 * this a history rather than a view of whatever happens to be running.
 *
 * One thing can be done to a meeting from here, and it is not an edit. There
 * is no way to change a meeting in this system: a meeting that is wrong is
 * cancelled, which releases everything it holds, and a new one is planned.
 *
 * A meeting whose coordinator is waiting at a gate is offered Resume first.
 * Whether its team is still alive does not matter: answering the gate revives
 * it, and the coordinator comes back knowing what it asked (R6).
 */
export default function MeetingsPage() {
  const [selected, setSelected] = useState<Meeting | null>(null);
  const [confirming, setConfirming] = useState<Meeting | null>(null);
  const cancellation = useCancelPlan();
  const team = useTeam();
  const navigate = useNavigate();
  const teams = useQuery({
    queryKey: ["teams"],
    queryFn: api.listTeams,
    refetchInterval: 30_000,
  });

  // Ours only, newest first. The server also holds runs of any other team card
  // loaded into it, and those have no coordinator of ours to read.
  const runs = (teams.data ?? [])
    .filter((run) => run.catalog_namespace === TEAM_NAMESPACE)
    .sort((a, b) => b.created_at.localeCompare(a.created_at));

  // One snapshot per run. Fine for a demo with tens of runs; a server-side
  // join is the remedy if it ever is not.
  const states = useQueries({
    queries: runs.map((run) => ({
      queryKey: ["coordinator", run.team_id],
      queryFn: () => api.coordinatorState(run.team_id),
    })),
  });

  // A run whose coordinator was never asked for anything has no meeting, so
  // there is nothing to list.
  const meetings: Meeting[] = runs.flatMap((run, index) => {
    const state = states[index]?.data;
    return state?.plan
      ? [{ teamId: run.team_id, createdAt: run.created_at, state, plan: state.plan }]
      : [];
  });
  const isLoading = teams.isLoading || states.some((query) => query.isLoading);
  const error = teams.error ?? states.find((query) => query.error)?.error ?? null;

  const columns: GridColDef[] = [
    { field: "title", headerName: "Title", flex: 1, minWidth: 180 },
    { field: "day", headerName: "Day", width: 120 },
    { field: "time", headerName: "Time", width: 130 },
    { field: "where", headerName: "Where", width: 160 },
    { field: "people", headerName: "People", width: 90 },
    {
      field: "status",
      headerName: "Status",
      width: 190,
      renderCell: (cell) => <StatusChip status={String(cell.value)} />,
    },
    {
      field: "waiting",
      headerName: "",
      width: 120,
      renderCell: (cell) =>
        cell.value ? <Chip size="small" variant="outlined" color="warning" label="your turn" /> : null,
    },
  ];

  const rows = meetings.map((meeting) => {
    const { plan } = meeting;
    return {
      id: meeting.teamId,
      title: plan.title,
      day: plan.day,
      time: plan.proposed_start
        ? `${plan.proposed_start.slice(0, 5)}–${plan.proposed_end?.slice(0, 5)}`
        : "—",
      where: plan.room_code ? `${plan.room_code} at ${plan.location_id}` : plan.location_id,
      people: plan.participant_emails.length,
      // A failure is not a status the plan derives - it lives beside the plan
      // in the coordinator's state - so the row says it in so many words.
      status: meeting.state.failure && !plan.cancelled ? "FAILED" : plan.status,
      waiting: waitingForTheHuman(meeting.state),
      meeting,
    };
  });

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Meetings
      </Typography>

      {isLoading && <CircularProgress />}
      {error && <Alert severity="error">{(error as Error).message}</Alert>}

      {!isLoading && meetings.length === 0 && (
        <Alert severity="info">No meetings yet. Ask the team for one first.</Alert>
      )}

      {meetings.length > 0 && (
        <DataGrid
          rows={rows}
          columns={columns}
          density="compact"
          autoHeight
          disableRowSelectionOnClick
          hideFooterSelectedRowCount
          onRowClick={(row) => setSelected(row.row.meeting as Meeting)}
          sx={{ "& .MuiDataGrid-row": { cursor: "pointer" } }}
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
          pageSizeOptions={[25, 50, 100]}
        />
      )}

      <MeetingDialog
        meeting={selected}
        onClose={() => setSelected(null)}
        onResume={async (teamId) => {
          setSelected(null);
          // A stopped team has to be restored before its stream will play.
          await api.restoreTeam(teamId);
          team.attach(teamId);
          navigate("/plan");
        }}
        onCancelMeeting={(meeting) => {
          setSelected(null);
          cancellation.reset();
          setConfirming(meeting);
        }}
      />

      <CancelDialog
        meeting={confirming}
        cancellation={cancellation}
        onClose={() => {
          setConfirming(null);
          cancellation.reset();
        }}
      />
    </Box>
  );
}

const COLOURS: Record<string, "default" | "info" | "success" | "warning" | "error"> = {
  DRAFT: "default",
  AWAITING_APPROVAL: "warning",
  APPROVED: "info",
  SCHEDULED: "info",
  ROOM_BOOKED: "info",
  CONFIRMED: "success",
  CANCELLED: "error",
  FAILED: "error",
};

function StatusChip({ status }: { status: string }) {
  return <Chip size="small" label={status.replaceAll("_", " ")} color={COLOURS[status] ?? "default"} />;
}

function MeetingDialog({
  meeting,
  onClose,
  onResume,
  onCancelMeeting,
}: {
  meeting: Meeting | null;
  onClose: () => void;
  onResume: (teamId: string) => void;
  onCancelMeeting: (meeting: Meeting) => void;
}) {
  const navigate = useNavigate();
  if (!meeting) return null;
  const { plan, state } = meeting;

  // Resumed by what the coordinator is waiting for, not by whether its team is
  // alive (R6): a stopped team is revived by the answer.
  const resumable = waitingForTheHuman(state);

  const rows: [string, string][] = [
    ["Day", plan.day],
    [
      "Time",
      plan.proposed_start
        ? `${plan.proposed_start.slice(0, 5)}–${plan.proposed_end?.slice(0, 5)}`
        : "not decided",
    ],
    ["Participants", plan.participant_emails.join(", ")],
    ["Location", plan.location_id],
    ["Room", plan.room_code ?? "none"],
    ["Lunch", plan.lunch_summary || (plan.with_lunch ? "not ordered" : "none wanted")],
    ["Asked for", plan.lunch_wish || "—"],
  ];

  // The ids are the whole point of the aggregate: nothing else in the system
  // records that this meeting, this room booking and this order belong
  // together, and a cancellation needs all three.
  const references: [string, string][] = [
    ["Plan", plan.plan_id],
    ["Meeting", plan.meeting_id === null ? "—" : String(plan.meeting_id)],
    ["Booking", plan.booking_id === null ? "—" : String(plan.booking_id)],
    ["Order", plan.order_id ?? "—"],
  ];

  return (
    <Dialog open fullWidth maxWidth="sm" onClose={onClose}>
      <DialogTitle sx={{ pb: 1 }}>
        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            {plan.title}
          </Typography>
          <StatusChip status={plan.status} />
        </Stack>
      </DialogTitle>
      <Divider />
      <DialogContent>
        <Fields rows={rows} />

        <Typography variant="subtitle2" sx={{ mt: 3 }}>
          Service references
        </Typography>
        <Fields rows={references} mono />

        {state.failure && !plan.cancelled && (
          <Alert severity="error" sx={{ mt: 3 }}>
            It could not be arranged: {state.failure}
          </Alert>
        )}

        {state.cancel_failures.length > 0 && (
          <Alert severity="warning" sx={{ mt: 3 }}>
            <Typography variant="body2" gutterBottom>
              Cancelled, but something is still held and needs releasing by hand:
            </Typography>
            <Stack component="ul" spacing={0.5} sx={{ pl: 2, m: 0 }}>
              {state.cancel_failures.map((line) => (
                <Typography component="li" variant="body2" key={line} sx={{ fontFamily: "monospace" }}>
                  {line}
                </Typography>
              ))}
            </Stack>
          </Alert>
        )}

        <Typography variant="subtitle2" sx={{ mt: 3 }}>
          The run
        </Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          One team arranges one meeting, and cancels it too - so everything that happened to
          this meeting is in one trace.
        </Typography>
        <Button
          variant="outlined"
          size="small"
          sx={{ mt: 1, justifyContent: "space-between", textTransform: "none", width: "100%" }}
          onClick={() => navigate(`/trace/${meeting.teamId}`)}
        >
          <span>Open the trace</span>
          <Box component="span" sx={{ fontFamily: "monospace", fontSize: 12 }}>
            {meeting.teamId}
          </Box>
        </Button>
      </DialogContent>
      <Divider />
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Typography variant="body2" color="text.secondary" sx={{ flexGrow: 1 }}>
          {resumable
            ? "This meeting is waiting for your answer."
            : "A meeting cannot be changed, only called off and planned again."}
        </Typography>
        <Button onClick={onClose}>Close</Button>
        <Button
          color="error"
          variant={resumable ? "text" : "outlined"}
          disabled={plan.cancelled}
          onClick={() => onCancelMeeting(meeting)}
        >
          Cancel meeting
        </Button>
        {resumable && (
          <Button variant="contained" onClick={() => onResume(meeting.teamId)}>
            Resume
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}

/** What this plan is holding, in words somebody can check before saying yes. */
function heldBy(plan: MeetingPlan): string[] {
  const held: string[] = [];
  if (plan.order_id) {
    held.push(plan.lunch_summary ? `the lunch order (${plan.lunch_summary})` : "the lunch order");
  }
  if (plan.booking_id !== null) {
    held.push(`the room ${plan.room_code ?? ""} at ${plan.location_id}`.replace("  ", " "));
  }
  if (plan.meeting_id !== null) {
    held.push(`the meeting in ${plan.participant_emails.length} agendas`);
  }
  return held;
}

/**
 * The confirmation, and then the run.
 *
 * The question is asked here rather than by the team, because the browser is
 * already holding the plan and can therefore answer it alone: nothing the
 * agents know would make this list any more accurate. The gates in front of
 * booking are the other way round - they need an answer the client does not
 * have (design_cancel.md §3).
 */
function CancelDialog({
  meeting,
  cancellation,
  onClose,
}: {
  meeting: Meeting | null;
  cancellation: ReturnType<typeof useCancelPlan>;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  if (!meeting) return null;
  const { plan } = meeting;

  const held = heldBy(plan);
  const failures = (cancellation.outcome?.failures as string[] | undefined) ?? [];
  const done = Boolean(cancellation.outcome);

  return (
    <Dialog open fullWidth maxWidth="sm" onClose={cancellation.running ? undefined : onClose}>
      <DialogTitle>Cancel “{plan.title}”?</DialogTitle>
      <DialogContent>
        {!done && (
          <>
            <DialogContentText>
              {held.length > 0
                ? "This releases everything the meeting holds:"
                : "Nothing has been booked for this meeting yet, so there is nothing to release."}
            </DialogContentText>
            <Stack component="ul" spacing={0.5} sx={{ mt: 1, pl: 3 }}>
              {held.map((item) => (
                <Typography component="li" variant="body2" key={item}>
                  {item}
                </Typography>
              ))}
            </Stack>
            <DialogContentText sx={{ mt: 2 }}>
              It cannot be undone. To meet anyway, plan a new meeting.
            </DialogContentText>
            {!plan.cancelled && plan.status !== "CONFIRMED" && (
              <Alert severity="info" sx={{ mt: 2 }}>
                This meeting is still being arranged. Anything its team books
                after this is released as soon as it lands.
              </Alert>
            )}
          </>
        )}

        {cancellation.running && (
          <Box sx={{ mt: 3 }}>
            <LinearProgress />
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Releasing them one at a time, in the order the services expect.
            </Typography>
          </Box>
        )}

        {cancellation.error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {cancellation.error}
          </Alert>
        )}

        {done && failures.length === 0 && (
          <Alert severity="success">The meeting is cancelled and everything was released.</Alert>
        )}

        {done && failures.length > 0 && (
          <Alert severity="warning">
            <Typography variant="body2" gutterBottom>
              The meeting is cancelled, but something is still held. These need releasing by hand:
            </Typography>
            <Stack component="ul" spacing={0.5} sx={{ pl: 2, m: 0 }}>
              {failures.map((line) => (
                <Typography component="li" variant="body2" key={line} sx={{ fontFamily: "monospace" }}>
                  {line}
                </Typography>
              ))}
            </Stack>
          </Alert>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        {cancellation.teamId && (
          <Button
            size="small"
            sx={{ mr: "auto" }}
            onClick={() => navigate(`/trace/${cancellation.teamId}`)}
          >
            Watch the trace
          </Button>
        )}
        <Button onClick={onClose} disabled={cancellation.running}>
          {done ? "Close" : "Keep it"}
        </Button>
        {!done && (
          <Button
            color="error"
            variant="contained"
            disabled={cancellation.running}
            onClick={() => void cancellation.run(meeting.teamId, plan)}
          >
            Cancel the meeting
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}

function Fields({ rows, mono = false }: { rows: [string, string][]; mono?: boolean }) {
  return (
    <Stack spacing={1}>
      {rows.map(([label, value]) => (
        <Stack direction="row" spacing={2} key={label}>
          <Typography variant="body2" color="text.secondary" sx={{ width: 120, flexShrink: 0 }}>
            {label}
          </Typography>
          <Typography
            variant="body2"
            sx={{ fontFamily: mono ? "monospace" : undefined, wordBreak: "break-all" }}
          >
            {value}
          </Typography>
        </Stack>
      ))}
    </Stack>
  );
}
