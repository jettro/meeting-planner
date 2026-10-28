import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  Stack,
  Typography,
} from "@mui/material";
import { DataGrid, type GridColDef } from "@mui/x-data-grid";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type MeetingPlan } from "../api/client";

/**
 * Every plan the team has made, including the ones nobody is watching.
 *
 * This reads the agents' own store through `GET /plans` rather than the event
 * stream: once a team has stopped there is no actor left to ask, and a history
 * that only works while a team is alive is not a history.
 *
 * Read-only, deliberately. Every change to a plan has compensations attached
 * to it, so every change goes through the agents.
 */
export default function PlansPage() {
  const [selected, setSelected] = useState<MeetingPlan | null>(null);
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

      <PlanDialog plan={selected} onClose={() => setSelected(null)} />
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

function PlanDialog({ plan, onClose }: { plan: MeetingPlan | null; onClose: () => void }) {
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
          One team plans one meeting, so a plan that is changed later has more than one.
          Each still has its full trace on the server.
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
