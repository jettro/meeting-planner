import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Collapse,
  Link,
  Stack,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  api,
  auth,
  conversationOf,
  type MemoryVersion,
  type Remembered,
} from "../api/client";

/**
 * What the planner remembers for you and about you (design_memory.md §4.8).
 *
 * Read-only on purpose (M14): it answers "where did it learn that?" - who said
 * it, in which conversation, and what it said before - and changes nothing.
 * Correcting is done by telling the planner, which is the path that records
 * who said it; editing here waits for the rules about who may (M11).
 */
export default function MemoryPage() {
  const memory = useQuery({ queryKey: ["my-memory"], queryFn: api.myMemory });
  // Names for the emails in `said_by`; an unknown email is shown as it is.
  const people = useQuery({ queryKey: ["people"], queryFn: auth.people, retry: false });
  const name = (email: string) => people.data?.find((person) => person.email === email)?.name ?? email;

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Memory
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        What the planner remembers between conversations: how you like to meet, and what people
        told it about you. To change something, tell the planner - it replaces the old version and
        keeps it in the history.
      </Typography>

      {memory.isLoading && <CircularProgress />}
      {memory.error && (
        <Alert severity="error">
          The server did not answer: {String((memory.error as Error).message)}
        </Alert>
      )}

      {memory.data && (
        <Stack spacing={4}>
          {!memory.data.journal && (memory.data.mine.length > 0 || memory.data.about_me.length > 0) && (
            <Alert severity="warning">
              No history is recorded for these items: the server has no git, or nothing was
              written through the planner yet.
            </Alert>
          )}
          <Section
            title="Mine"
            empty="Nothing yet. Tell the planner who your team is, or how long your stand-ups last."
            items={memory.data.mine}
            me={memory.data.email}
            name={name}
          />
          <Section
            title="About me"
            empty="Nobody has told the planner anything about you."
            items={memory.data.about_me}
            me={memory.data.email}
            name={name}
          />
        </Stack>
      )}
    </Box>
  );
}

interface SectionProps {
  title: string;
  empty: string;
  items: Remembered[];
  me: string;
  name: (email: string) => string;
}

function Section({ title, empty, items, me, name }: SectionProps) {
  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        {title}
      </Typography>
      {items.length === 0 ? (
        <Typography color="text.secondary">{empty}</Typography>
      ) : (
        <Stack spacing={2}>
          {items.map((remembered) => (
            <Item key={remembered.item.id} remembered={remembered} me={me} name={name} />
          ))}
        </Stack>
      )}
    </Box>
  );
}

function Item({ remembered, me, name }: { remembered: Remembered; me: string; name: (email: string) => string }) {
  const [open, setOpen] = useState(false);
  const { item, recorded, history } = remembered;

  return (
    <Card variant="outlined">
      <CardContent>
        <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 1 }}>
          <Typography sx={{ fontWeight: 600, flexGrow: 1 }}>{item.situation}</Typography>
          <Chip label={item.kind} size="small" variant="outlined" />
          {item.status !== "confirmed" && <Chip label={item.status} size="small" color="warning" />}
        </Stack>
        <Typography sx={{ mb: 1 }}>{item.text}</Typography>
        <Origin version={recorded ?? { item, changed: null, by: "", outside: false }} me={me} name={name} />

        {history.length > 0 && (
          <>
            <Button size="small" sx={{ mt: 1, px: 0 }} onClick={() => setOpen(!open)}>
              {open ? "Hide history" : `History (${history.length})`}
            </Button>
            <Collapse in={open}>
              <Stack spacing={1} sx={{ mt: 1, pl: 2, borderLeft: 2, borderColor: "divider" }}>
                {history.map((version) => (
                  <Box key={version.item.id}>
                    <Typography variant="body2" sx={{ textDecoration: "line-through" }}>
                      {version.item.text}
                    </Typography>
                    <Origin version={version} me={me} name={name} />
                  </Box>
                ))}
              </Stack>
            </Collapse>
          </>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Who said it, when, and where.
 *
 * The conversation is linked only when it is the reader's own: one someone
 * else had is theirs, and the server would answer 404 to anyone else.
 */
function Origin({ version, me, name }: { version: MemoryVersion; me: string; name: (email: string) => string }) {
  const navigate = useNavigate();
  const { item } = version;
  const when = version.changed ? new Date(version.changed).toLocaleString() : item.written;
  const conversation = conversationOf(item);
  const mine = item.said_by === me;

  return (
    <Typography variant="body2" color="text.secondary">
      {version.outside ? "Changed outside the planner" : `Said by ${mine ? "you" : name(item.said_by)}`}, {when}
      {conversation &&
        (mine ? (
          <>
            {" - "}
            <Link component="button" variant="body2" onClick={() => navigate(`/trace/${conversation}`)}>
              see the conversation
            </Link>
          </>
        ) : (
          " - in their conversation"
        ))}
    </Typography>
  );
}
