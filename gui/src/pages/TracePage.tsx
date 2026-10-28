import {
  Alert,
  Box,
  Button,
  Chip,
  FormControlLabel,
  Stack,
  Switch,
  Typography,
} from "@mui/material";
import { DataGrid, type GridColDef } from "@mui/x-data-grid";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, isDomainEvent, shortName, summarise, type TeamEvent } from "../api/client";
import { EventDetails } from "../components/EventDetails";
import { useTeam } from "../TeamContext";

/**
 * Everything the team said, in order.
 *
 * Two views, because there are two audiences for the same stream. The
 * conversation is the agents talking to each other - `SentMessage` wrapping one
 * of our typed messages, which is the story of a meeting being arranged. The
 * framework view adds what the framework says about itself: starts, receipts,
 * model calls. That second one is why this screen exists at all (§1).
 *
 * The grid shows a one-line summary of the payload, which is enough to
 * recognise a message but never enough to read one. Clicking a row opens the
 * whole thing.
 *
 * Two sources, one screen. Without a team in the URL this is the live stream
 * of the plan being watched. With one - how the Meetings screen links here - it
 * is that run's stored trace, fetched once, because the events outlive both
 * the socket and the team that produced them.
 */
/** Stable, so an unfetched replay does not look like new events every render. */
const NOTHING: TeamEvent[] = [];

export default function TracePage() {
  const { teamId: routeTeamId } = useParams();
  const live = useTeam();
  const [showFramework, setShowFramework] = useState(false);
  const [selected, setSelected] = useState<TeamEvent | null>(null);

  const replaying = Boolean(routeTeamId) && routeTeamId !== live.teamId;
  const stored = useQuery({
    queryKey: ["team-events", routeTeamId],
    queryFn: () => api.teamEvents(routeTeamId!),
    enabled: replaying,
  });

  const teamId = replaying ? routeTeamId! : live.teamId;
  const events = replaying ? (stored.data ?? NOTHING) : live.events;
  const connected = !replaying && live.connected;

  const rows = useMemo(() => {
    const visible = showFramework ? events : events.filter(isDomainEvent);
    return visible.map((event, index) => ({
      id: event.id,
      step: index + 1,
      time: event.timestamp?.slice(11, 19) ?? "",
      from: event.sender?.name ?? "",
      to: event.recipient?.name ?? "",
      kind: describe(event),
      summary: summarise(event),
      event,
    }));
  }, [events, showFramework]);

  const columns: GridColDef[] = [
    { field: "step", headerName: "#", width: 70 },
    { field: "time", headerName: "Time", width: 100 },
    { field: "from", headerName: "From", width: 160 },
    { field: "to", headerName: "To", width: 160 },
    { field: "kind", headerName: "Message", width: 200 },
    { field: "summary", headerName: "Contents", flex: 1, minWidth: 280 },
  ];

  if (!teamId) {
    return (
      <Alert severity="info">
        No team yet. Start a plan and the conversation shows up here as it happens, or
        open one from <Link to="/meetings">Meetings</Link>.
      </Alert>
    );
  }

  if (replaying && stored.isError) {
    return (
      <Alert severity="error">
        That run's trace could not be read: {(stored.error as Error).message}
      </Alert>
    );
  }

  return (
    <Box>
      <Stack direction="row" spacing={2} sx={{ alignItems: "center", mb: 2 }}>
        <Typography variant="h5" sx={{ flexGrow: 1 }}>
          Trace
        </Typography>
        <Chip
          size="small"
          color={connected ? "success" : "default"}
          label={replaying ? `run ${teamId.slice(0, 8)}` : connected ? "live" : "disconnected"}
        />
        {replaying && (
          <Button size="small" component={Link} to="/trace">
            Back to the live run
          </Button>
        )}
        <FormControlLabel
          control={
            <Switch
              checked={showFramework}
              onChange={(event) => setShowFramework(event.target.checked)}
            />
          }
          label="Framework events"
        />
      </Stack>

      <DataGrid
        rows={rows}
        columns={columns}
        density="compact"
        disableRowSelectionOnClick
        autoHeight
        hideFooterSelectedRowCount
        onRowClick={(row) => setSelected(row.row.event as TeamEvent)}
        sx={{ "& .MuiDataGrid-row": { cursor: "pointer" } }}
        initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
        pageSizeOptions={[25, 50, 100]}
      />

      {/* Keyed on the event, so opening another row starts on Fields again
          rather than wherever the last one was left. */}
      <EventDetails
        key={selected?.id}
        event={selected}
        onClose={() => setSelected(null)}
      />
    </Box>
  );
}

/** A domain message by its own name; anything else by what the framework calls it. */
function describe(event: TeamEvent): string {
  return isDomainEvent(event)
    ? shortName(event.message?.__model__)
    : shortName(event.__model__);
}
