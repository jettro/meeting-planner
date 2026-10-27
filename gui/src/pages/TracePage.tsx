import {
  Alert,
  Box,
  Chip,
  FormControlLabel,
  Stack,
  Switch,
  Typography,
} from "@mui/material";
import { DataGrid, type GridColDef } from "@mui/x-data-grid";
import { useMemo, useState } from "react";
import { isDomainEvent, shortName, type TeamEvent } from "../api/client";
import { useTeam } from "../TeamContext";

/**
 * Everything the team said, in order.
 *
 * Two views, because there are two audiences for the same stream. The
 * conversation is the agents talking to each other - `SentMessage` wrapping one
 * of our typed messages, which is the story of a meeting being arranged. The
 * framework view adds what the framework says about itself: starts, receipts,
 * model calls. That second one is why this screen exists at all (§1).
 */
export default function TracePage() {
  const { teamId, events, connected } = useTeam();
  const [showFramework, setShowFramework] = useState(false);

  const rows = useMemo(() => {
    const visible = showFramework ? events : events.filter(isDomainEvent);
    return visible.map((event, index) => ({
      id: event.id,
      step: index + 1,
      time: event.timestamp?.slice(11, 19) ?? "",
      from: event.sender?.name ?? "",
      to: event.recipient?.name ?? "",
      kind: describe(event),
      envelope: shortName(event.__model__),
    }));
  }, [events, showFramework]);

  const columns: GridColDef[] = [
    { field: "step", headerName: "#", width: 70 },
    { field: "time", headerName: "Time", width: 100 },
    { field: "from", headerName: "From", width: 160 },
    { field: "to", headerName: "To", width: 160 },
    { field: "kind", headerName: "Message", flex: 1, minWidth: 220 },
    { field: "envelope", headerName: "Envelope", width: 170 },
  ];

  if (!teamId) {
    return (
      <Alert severity="info">
        No team yet. Start a plan and the conversation shows up here as it happens.
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
          label={connected ? "live" : "disconnected"}
        />
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
        initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
        pageSizeOptions={[25, 50, 100]}
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
