import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Link,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  api,
  auth,
  conversationOf,
  ON_THE_PAGE,
  type MemoryVersion,
  type MemoryItem,
  type MyMemory,
  type ProposalView,
  type Remembered,
  type Suggestion,
} from "../api/client";

/**
 * What the planner remembers for you, about you, and about places (design_memory.md §4.8, §10.4).
 *
 * It answers "where did it learn that?" - who said it, in which conversation,
 * and what it said before - and lets you change what is yours to change (M22):
 * your own items, what is said about you, what you said about others, and the
 * place facts you said. The buttons follow the server's `can_change`; the
 * server checks again. An edit is a new version, so the history keeps the old
 * words; a delete takes the item out of memory and leaves the history alone.
 */
export default function MemoryPage() {
  const memory = useQuery({ queryKey: ["my-memory"], queryFn: api.myMemory });
  const queryClient = useQueryClient();
  // The keeper run being watched, if any: its state is polled until it is done (M44).
  const [keeperTeam, setKeeperTeam] = useState<string | null>(null);
  const tidy = useMutation({ mutationFn: api.startKeeper, onSuccess: setKeeperTeam });
  const keeper = useQuery({
    queryKey: ["keeper", keeperTeam],
    queryFn: () => api.keeperState(keeperTeam as string),
    enabled: keeperTeam !== null,
    refetchInterval: (query) => (query.state.data?.done ? false : 1500),
  });
  const keeperDone = keeper.data?.done ?? false;
  useEffect(() => {
    if (keeperDone) void queryClient.invalidateQueries({ queryKey: ["my-memory"] });
  }, [keeperDone, queryClient]);
  const tidying = tidy.isPending || (keeperTeam !== null && !keeperDone);
  // Names for the emails in `said_by`; an unknown email is shown as it is.
  const people = useQuery({ queryKey: ["people"], queryFn: auth.people, retry: false });
  const name = (email: string) => people.data?.find((person) => person.email === email)?.name ?? email;

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Memory
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        What the planner remembers between conversations: how you like to meet, what people told
        it about you, what you told it about others, and what anyone told it about a place. You can
        change or delete what is yours; the history keeps every earlier version.
      </Typography>

      {memory.isLoading && <CircularProgress />}
      {memory.error && (
        <Alert severity="error">
          The server did not answer: {String((memory.error as Error).message)}
        </Alert>
      )}

      {memory.data && (
        <Stack spacing={4}>
          {!memory.data.journal &&
            [memory.data.mine, memory.data.about_me, memory.data.said_by_me, memory.data.places].some(
              (list) => list.length > 0,
            ) && (
            <Alert severity="warning">
              No history is recorded for these items: the server has no git, or nothing was
              written through the planner yet.
            </Alert>
          )}
          {memory.data.suggestions.length > 0 && (
            <Box>
              <Typography variant="h6" gutterBottom>
                Suggestions
              </Typography>
              <Typography color="text.secondary" sx={{ mb: 2 }}>
                Things you keep repeating in your meetings. Nothing is remembered until you say so.
              </Typography>
              <Stack spacing={2}>
                {memory.data.suggestions.map((suggestion) => (
                  <SuggestionCard key={suggestion.key} suggestion={suggestion} name={name} />
                ))}
              </Stack>
            </Box>
          )}
          {memory.data.proposals.length > 0 && (
            <Box>
              <Typography variant="h6" gutterBottom>
                Proposed by the memory keeper
              </Typography>
              <Typography color="text.secondary" sx={{ mb: 2 }}>
                Ways to tidy what is in Mine. Nothing changes until you accept it.
              </Typography>
              <Stack spacing={2}>
                {memory.data.proposals.map((view) => (
                  <ProposalCard key={view.proposal.id} view={view} />
                ))}
              </Stack>
            </Box>
          )}
          <Section
            title="Mine"
            empty="Nothing yet. Tell the planner who your team is, or how long your stand-ups last."
            items={memory.data.mine}
            me={memory.data.email}
            name={name}
            action={
              memory.data.mine.length > 0 && (
                <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                  {keeper.data?.done && !keeper.data.failure && (
                    <Typography variant="body2" color="text.secondary">
                      {/* What is still open, not what the run found: answered ones are gone. */}
                      {keeper.data.proposed === 0
                        ? "Nothing to tidy."
                        : memory.data.proposals.length > 0
                          ? `${memory.data.proposals.length} proposal${memory.data.proposals.length === 1 ? "" : "s"} above.`
                          : "All answered."}
                    </Typography>
                  )}
                  {keeper.data?.failure && (
                    <Typography variant="body2" color="error">
                      The keeper could not finish: {keeper.data.failure}
                    </Typography>
                  )}
                  <Button
                    size="small"
                    variant="outlined"
                    disabled={tidying}
                    startIcon={tidying ? <CircularProgress size={14} /> : undefined}
                    onClick={() => {
                      setKeeperTeam(null);
                      tidy.mutate();
                    }}
                  >
                    {tidying ? "Tidying…" : "Tidy up"}
                  </Button>
                </Stack>
              )
            }
          />
          <Section
            title="About me"
            empty="Nobody has told the planner anything about you."
            items={memory.data.about_me}
            me={memory.data.email}
            name={name}
          />
          <Section
            title="Said by me"
            empty="You have not told the planner anything about someone else."
            items={memory.data.said_by_me}
            me={memory.data.email}
            name={name}
            showWho
          />
          <Section
            title="Places"
            empty="Nobody has told the planner anything about a place yet."
            items={memory.data.places}
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
  /** Name the person each item is about - for what you said about others. */
  showWho?: boolean;
  /** Something to do with the whole list, beside its title. */
  action?: React.ReactNode;
}

function Section({ title, empty, items, me, name, showWho = false, action }: SectionProps) {
  return (
    <Box>
      <Stack direction="row" spacing={2} sx={{ alignItems: "center", mb: 1 }}>
        <Typography variant="h6" sx={{ flexGrow: 1 }}>
          {title}
        </Typography>
        {action}
      </Stack>
      {items.length === 0 ? (
        <Typography color="text.secondary">{empty}</Typography>
      ) : (
        <Stack spacing={2}>
          {items.map((remembered) => (
            <Item key={remembered.item.id} remembered={remembered} me={me} name={name} showWho={showWho} />
          ))}
        </Stack>
      )}
    </Box>
  );
}

/** What a proposal would change, in words (design_memory.md M40). */
const PROPOSAL_TITLE = { merge: "Merge", retire: "Retire", reword: "Reword" } as const;

/**
 * One of the keeper's proposals: the items it would change struck through, the
 * new words beside them, its reason, and the answer (M42, M43).
 */
function ProposalCard({ view }: { view: ProposalView }) {
  const queryClient = useQueryClient();
  const redraw = (memory: MyMemory) => queryClient.setQueryData(["my-memory"], memory);
  const accept = useMutation({ mutationFn: () => api.acceptProposal(view.proposal.id), onSuccess: redraw });
  const decline = useMutation({ mutationFn: () => api.declineProposal(view.proposal.id), onSuccess: redraw });
  const { proposal, targets } = view;
  const struck = (item: MemoryItem) => (
    <Typography key={item.id} variant="body2" sx={{ textDecoration: "line-through" }}>
      <strong>{item.situation}</strong>: {item.text}
    </Typography>
  );

  return (
    <Card variant="outlined" sx={{ borderColor: "primary.main" }}>
      <CardContent>
        <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 1 }}>
          <Typography sx={{ fontWeight: 600, flexGrow: 1 }}>{PROPOSAL_TITLE[proposal.kind]}</Typography>
          <Chip label="memory keeper" size="small" variant="outlined" />
        </Stack>
        <Typography color="text.secondary" sx={{ mb: 1 }}>
          {proposal.reason}
        </Typography>
        <Stack spacing={0.5} sx={{ pl: 2, borderLeft: 2, borderColor: "divider", mb: 1 }}>
          {targets.map(struck)}
          {proposal.kind !== "retire" && (
            <Typography variant="body2">
              <strong>{proposal.situation}</strong>: {proposal.text}
            </Typography>
          )}
        </Stack>
        <Stack direction="row" spacing={1}>
          <Button variant="contained" size="small" disabled={accept.isPending} onClick={() => accept.mutate()}>
            Accept
          </Button>
          <Button size="small" disabled={decline.isPending} onClick={() => decline.mutate()}>
            Not now
          </Button>
        </Stack>
        {(accept.error || decline.error) && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {reasonOf(accept.error ?? decline.error)}
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}

/** A list of names: "A, B and C". */
function listed(names: string[]): string {
  return names.length < 2 ? names.join("") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

/**
 * One offer, answered here (design_memory.md M34, M35). A team needs a name -
 * only you can give it; a meal can be changed before it is remembered.
 */
function SuggestionCard({ suggestion, name }: { suggestion: Suggestion; name: (email: string) => string }) {
  const queryClient = useQueryClient();
  const [teamName, setTeamName] = useState("");
  const [wish, setWish] = useState(suggestion.wish);
  const redraw = (memory: MyMemory) => queryClient.setQueryData(["my-memory"], memory);
  const accept = useMutation({
    mutationFn: () =>
      api.acceptSuggestion(suggestion.key, suggestion.kind === "team" ? { name: teamName } : { text: wish }),
    onSuccess: redraw,
  });
  const decline = useMutation({ mutationFn: () => api.declineSuggestion(suggestion.key), onSuccess: redraw });
  const team = suggestion.kind === "team";
  const ready = team ? teamName.trim() !== "" : wish.trim() !== "";

  return (
    <Card variant="outlined" sx={{ borderColor: "primary.main" }}>
      <CardContent>
        <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 1 }}>
          <Typography sx={{ fontWeight: 600, flexGrow: 1 }}>
            {team ? "A team?" : `Lunch for "${suggestion.title}"?`}
          </Typography>
          <Chip label={`${suggestion.meetings} meetings`} size="small" variant="outlined" />
        </Stack>
        <Typography sx={{ mb: 2 }}>
          {team
            ? `You met with ${listed(suggestion.people.map(name))} in ${suggestion.meetings} meetings. Give them a name, and next time the name is enough.`
            : `Your meetings called "${suggestion.title}" had a lunch wish ${suggestion.meetings} times. Remember it, and the planner fills it in next time.`}
        </Typography>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ alignItems: { sm: "center" } }}>
          {team ? (
            <TextField
              label="Team name"
              placeholder="the design team"
              size="small"
              value={teamName}
              onChange={(event) => setTeamName(event.target.value)}
              sx={{ flexGrow: 1 }}
            />
          ) : (
            <TextField
              label="Lunch"
              size="small"
              value={wish}
              onChange={(event) => setWish(event.target.value)}
              sx={{ flexGrow: 1 }}
            />
          )}
          <Button variant="contained" size="small" disabled={!ready || accept.isPending} onClick={() => accept.mutate()}>
            Remember this
          </Button>
          <Button size="small" disabled={decline.isPending} onClick={() => decline.mutate()}>
            Not now
          </Button>
        </Stack>
        {(accept.error || decline.error) && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {reasonOf(accept.error ?? decline.error)}
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}

/** The server's reason for a refused change, from its `{"detail": ...}`, or the raw message. */
function reasonOf(error: unknown): string {
  const message = String((error as Error)?.message ?? error);
  try {
    const detail = (JSON.parse(message) as { detail?: unknown }).detail;
    return typeof detail === "string" ? detail : message;
  } catch {
    return message;
  }
}

interface ItemProps {
  remembered: Remembered;
  me: string;
  name: (email: string) => string;
  showWho: boolean;
}

function Item({ remembered, me, name, showWho }: ItemProps) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [situation, setSituation] = useState("");
  const [text, setText] = useState("");
  const queryClient = useQueryClient();
  const { item, recorded, history, can_change } = remembered;

  // Each change answers with the whole memory as it is now on disk.
  const redraw = (memory: MyMemory) => queryClient.setQueryData(["my-memory"], memory);
  const edit = useMutation({
    mutationFn: () => api.editMemoryItem(item.id, { situation, text }),
    onSuccess: (memory) => {
      setEditing(false);
      redraw(memory);
    },
  });
  const remove = useMutation({
    mutationFn: () => api.deleteMemoryItem(item.id),
    onSuccess: (memory) => {
      setConfirming(false);
      redraw(memory);
    },
  });

  const startEditing = () => {
    setSituation(item.situation);
    setText(item.text);
    edit.reset();
    setEditing(true);
  };

  return (
    <Card variant="outlined">
      <CardContent>
        <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 1 }}>
          <Typography sx={{ fontWeight: 600, flexGrow: 1 }}>{item.situation}</Typography>
          {showWho && item.scope.startsWith("person:") && (
            <Chip label={`about ${name(item.scope.slice("person:".length))}`} size="small" />
          )}
          {item.scope.startsWith("place:") && (
            <Chip label={item.scope.slice("place:".length)} size="small" />
          )}
          <Chip label={item.kind} size="small" variant="outlined" />
          {item.status !== "confirmed" && <Chip label={item.status} size="small" color="warning" />}
        </Stack>

        {editing ? (
          <Stack spacing={2} sx={{ my: 1 }}>
            <TextField
              label="When it applies"
              size="small"
              value={situation}
              onChange={(event) => setSituation(event.target.value)}
            />
            <TextField
              label="What to remember"
              size="small"
              multiline
              minRows={2}
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
            {edit.error && <Alert severity="error">{reasonOf(edit.error)}</Alert>}
            <Stack direction="row" spacing={1}>
              <Button
                variant="contained"
                size="small"
                disabled={edit.isPending || !situation.trim() || !text.trim()}
                onClick={() => edit.mutate()}
              >
                Save
              </Button>
              <Button size="small" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </Stack>
          </Stack>
        ) : (
          <>
            <Typography sx={{ mb: 1 }}>{item.text}</Typography>
            <Origin version={recorded ?? { item, changed: null, by: "", outside: false }} me={me} name={name} />
          </>
        )}

        <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
          {history.length > 0 && (
            <Button size="small" sx={{ px: 0 }} onClick={() => setOpen(!open)}>
              {open ? "Hide history" : `History (${history.length})`}
            </Button>
          )}
          <Box sx={{ flexGrow: 1 }} />
          {can_change && !editing && (
            <>
              <Button size="small" onClick={startEditing}>
                Edit
              </Button>
              <Button size="small" color="error" onClick={() => setConfirming(true)}>
                Delete
              </Button>
            </>
          )}
        </Stack>

        {history.length > 0 && (
          <Collapse in={open}>
            <Stack spacing={1} sx={{ mt: 1, pl: 2, borderLeft: 2, borderColor: "divider" }}>
              {history.map((version) => (
                <Box key={version.item.id}>
                  <Typography variant="body2" sx={{ textDecoration: "line-through" }}>
                    {version.item.situation !== item.situation && `${version.item.situation}: `}
                    {version.item.text}
                  </Typography>
                  <Origin version={version} me={me} name={name} />
                </Box>
              ))}
            </Stack>
          </Collapse>
        )}
      </CardContent>

      <Dialog open={confirming} onClose={() => setConfirming(false)}>
        <DialogTitle>Delete this from memory?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            <strong>{item.situation}</strong>: {item.text}
          </DialogContentText>
          <DialogContentText sx={{ mt: 2 }}>
            The planner stops using it at once. Its earlier versions stay in the journal.
          </DialogContentText>
          {remove.error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {reasonOf(remove.error)}
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirming(false)}>Keep it</Button>
          <Button color="error" disabled={remove.isPending} onClick={() => remove.mutate()}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Card>
  );
}

/**
 * Who said it, when, and where.
 *
 * The conversation is linked only when it is the reader's own: one someone
 * else had is theirs, and the server would answer 404 to anyone else. A change
 * made on this page names the page instead.
 */
function Origin({ version, me, name }: { version: MemoryVersion; me: string; name: (email: string) => string }) {
  const navigate = useNavigate();
  const { item } = version;
  const when = version.changed ? new Date(version.changed).toLocaleString() : item.written;
  const conversation = conversationOf(item);
  const mine = item.said_by === me;
  const who = mine ? "you" : name(item.said_by);

  if (version.outside) {
    return (
      <Typography variant="body2" color="text.secondary">
        Changed outside the planner, {when}
      </Typography>
    );
  }
  if (item.evidence === ON_THE_PAGE) {
    return (
      <Typography variant="body2" color="text.secondary">
        Changed on the Memory page by {who}, {when}
      </Typography>
    );
  }
  return (
    <Typography variant="body2" color="text.secondary">
      Said by {who}, {when}
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
