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
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type MeetingPlan } from "../api/client";
import { useCancelPlan } from "../hooks/useCancelPlan";

/**
 * Every plan the team has made, including the ones nobody is watching.
 *
 * This reads the agents' own store through `GET /plans` rather than the event
 * stream: once a team has stopped there is no actor left to ask, and a history
 * that only works while a team is alive is not a history.
 *
 * One thing can be done to a plan from here, and it is not an edit. There is
 * no way to change a meeting in this system: a meeting that is wrong is
 * cancelled, which releases everything it holds, and a new one is planned.
 */
export default function PlansPage() {
  const [selected, setSelected] = useState<MeetingPlan | null>(null);
  const [confirming, setConfirming] = useState<MeetingPlan | null>(null);
  const cancellation = useCancelPlan();
  const { data, isLoading, error } = useQuery({
    queryKey: ["plans"],
    queryFn: api.plans,
  });

  const columns: GridColDef[] = [
    { field: "title", headerName: "Title", flex: 1, minWidth: 180 },
    { field: "day", headerName: "Day", width: 120 },
    { field: "time", headerName: "Time", width: 130 },
    { field: "where", headerName: "Where", width: 160 },
    { field: "people", headerName: "People", width: 90 },
    {
      field: "status",
      headerName: "Status",
      width: 170,
      renderCell: (cell) => <StatusChip status={String(cell.value)} />,
    },
  ];

  const rows = (data ?? []).map((plan) => ({
    id: plan.plan_id,
    title: plan.title,
    day: plan.day,
    time: plan.proposed_start
      ? `${plan.proposed_start.slice(0, 5)}–${plan.proposed_end?.slice(0, 5)}`
      : "—",
    where: plan.room_code ? `${plan.room_code} at ${plan.location_id}` : plan.location_id,
    people: plan.participant_emails.length,
    status: plan.status,
    plan,
  }));

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Plans
      </Typography>

      {isLoading && <CircularProgress />}
      {error && <Alert severity="error">{(error as Error).message}</Alert>}

      {data && data.length === 0 && (
        <Alert severity="info">No plans yet. Ask the team for a meeting first.</Alert>
      )}

      {data && data.length > 0 && (
        <DataGrid
          rows={rows}
          columns={columns}
          density="compact"
          autoHeight
          disableRowSelectionOnClick
          hideFooterSelectedRowCount
          onRowClick={(row) => setSelected(row.row.plan as MeetingPlan)}
          sx={{ "& .MuiDataGrid-row": { cursor: "pointer" } }}
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
          pageSizeOptions={[25, 50, 100]}
        />
      )}

      <PlanDialog
        plan={selected}
        onClose={() => setSelected(null)}
        onCancelMeeting={(plan) => {
          setSelected(null);
          cancellation.reset();
          setConfirming(plan);
        }}
      />

      <CancelDialog
        plan={confirming}
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
};

function StatusChip({ status }: { status: string }) {
  return <Chip size="small" label={status.replace("_", " ")} color={COLOURS[status] ?? "default"} />;
}

function PlanDialog({
  plan,
  onClose,
  onCancelMeeting,
}: {
  plan: MeetingPlan | null;
  onClose: () => void;
  onCancelMeeting: (plan: MeetingPlan) => void;
}) {
  const navigate = useNavigate();
  if (!plan) return null;

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

        <Typography variant="subtitle2" sx={{ mt: 3 }}>
          Runs
        </Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          One team plans one meeting, so a plan that is cancelled later has a second run —
          the team that released it. Each still has its full trace on the server.
        </Typography>
        <Stack spacing={1} sx={{ mt: 1 }}>
          {plan.team_ids.length === 0 && (
            <Typography variant="body2">
              This plan predates run tracking, so its trace cannot be found.
            </Typography>
          )}
          {plan.team_ids.map((teamId, index) => (
            <Button
              key={teamId}
              variant="outlined"
              size="small"
              sx={{ justifyContent: "space-between", textTransform: "none" }}
              onClick={() => navigate(`/trace/${teamId}`)}
            >
              <span>Run {index + 1}</span>
              <Box component="span" sx={{ fontFamily: "monospace", fontSize: 12 }}>
                {teamId}
              </Box>
            </Button>
          ))}
        </Stack>
      </DialogContent>
      <Divider />
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Typography variant="body2" color="text.secondary" sx={{ flexGrow: 1 }}>
          A meeting cannot be changed, only called off and planned again.
        </Typography>
        <Button onClick={onClose}>Close</Button>
        <Button
          color="error"
          variant="outlined"
          disabled={plan.cancelled}
          onClick={() => onCancelMeeting(plan)}
        >
          Cancel meeting
        </Button>
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
  plan,
  cancellation,
  onClose,
}: {
  plan: MeetingPlan | null;
  cancellation: ReturnType<typeof useCancelPlan>;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  if (!plan) return null;

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
            onClick={() => void cancellation.run(plan)}
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
