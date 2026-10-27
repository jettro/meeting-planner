import {
  Box,
  Chip,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  Stack,
  Tab,
  Tabs,
  Typography,
} from "@mui/material";
import { useState } from "react";
import { contentOf, shortName, type TeamEvent } from "../api/client";

/**
 * One event, in full.
 *
 * Two views on purpose. "Fields" is the payload with the plumbing stripped -
 * what the message actually says, which is the question this screen is for.
 * "Raw" is the envelope exactly as it came off the socket, because the moment
 * something looks wrong the pretty version is the first thing to distrust.
 */
export function EventDetails({
  event,
  onClose,
}: {
  event: TeamEvent | null;
  onClose: () => void;
}) {
  const [tab, setTab] = useState(0);
  if (!event) return null;

  const fields = contentOf(event);
  const inner = event.message?.__model__;

  return (
    <Dialog open fullWidth maxWidth="md" onClose={onClose}>
      <DialogTitle sx={{ pb: 1 }}>
        <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
          <Typography variant="h6">{shortName(inner ?? event.__model__)}</Typography>
          {inner && <Chip size="small" label={shortName(event.__model__)} />}
        </Stack>
        <Typography variant="body2" color="text.secondary">
          {event.sender?.name ?? "—"}
          {event.recipient?.name ? ` → ${event.recipient.name}` : ""} ·{" "}
          {event.timestamp?.replace("T", " ").slice(0, 19)}
        </Typography>
      </DialogTitle>
      <Tabs value={tab} onChange={(_, next) => setTab(next)} sx={{ px: 3 }}>
        <Tab label="Fields" />
        <Tab label="Raw" />
      </Tabs>
      <Divider />
      <DialogContent>
        {tab === 0 ? <Fields fields={fields} /> : <Raw value={event} />}
      </DialogContent>
    </Dialog>
  );
}

function Fields({ fields }: { fields: Record<string, unknown> }) {
  const entries = Object.entries(fields);
  if (entries.length === 0) {
    return (
      <Typography color="text.secondary">
        This event carries no payload of its own.
      </Typography>
    );
  }

  return (
    <Stack spacing={1.5}>
      {entries.map(([key, value]) => (
        <Stack key={key} direction={{ xs: "column", sm: "row" }} spacing={2}>
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ minWidth: 160, flexShrink: 0 }}
          >
            {key}
          </Typography>
          <Value value={value} />
        </Stack>
      ))}
    </Stack>
  );
}

function Value({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === "") {
    return <Typography variant="body2">—</Typography>;
  }
  if (typeof value === "object") {
    return <Raw value={value} dense />;
  }
  return (
    <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>
      {String(value)}
    </Typography>
  );
}

function Raw({ value, dense = false }: { value: unknown; dense?: boolean }) {
  return (
    <Box
      component="pre"
      sx={{
        m: 0,
        p: 1.5,
        borderRadius: 1,
        bgcolor: "grey.100",
        fontSize: dense ? 12 : 13,
        overflowX: "auto",
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
      }}
    >
      {JSON.stringify(value, null, 2)}
    </Box>
  );
}
