import {
  Button,
  Card,
  CardContent,
  FormControl,
  FormControlLabel,
  Radio,
  RadioGroup,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useState } from "react";
import {
  LUNCH_QUESTION,
  SLOT_QUESTION,
  type DomainMessage,
  type LunchQuestion,
  type SlotQuestion,
} from "../api/client";

/**
 * The two gates, rendered from the question itself.
 *
 * The slot answer is an index into candidates that travel *with* the question,
 * which is exactly why a browser can show radio buttons and still send "2":
 * the structure is in the question, not in the answer (design_gui.md §4.1).
 *
 * The lunch answer is free text and stays that way. Nothing here tries to
 * understand it - @Catering holds the menu, and it is the only agent that
 * should be reading the words (D9).
 */
export function GatePrompt({
  question,
  onAnswer,
}: {
  question: DomainMessage;
  onAnswer: (content: string) => void;
}) {
  if (question.__model__ === SLOT_QUESTION) {
    return <SlotGate question={question as SlotQuestion} onAnswer={onAnswer} />;
  }
  if (question.__model__ === LUNCH_QUESTION) {
    return <LunchGate question={question as LunchQuestion} onAnswer={onAnswer} />;
  }
  return null;
}

function SlotGate({
  question,
  onAnswer,
}: {
  question: SlotQuestion;
  onAnswer: (content: string) => void;
}) {
  const [choice, setChoice] = useState("1");

  return (
    <Card variant="outlined" sx={{ borderColor: "primary.main" }}>
      <CardContent>
        <Typography variant="h6">When should it be?</Typography>
        <Typography color="text.secondary" gutterBottom>
          {question.title}
          {question.location_name ? ` at ${question.location_name}` : ""} on {question.day}.
          Nothing is booked yet.
        </Typography>
        {question.location_name && (
          // The team chose the place from a description, so the choice is
          // shown with its reason: approving the time approves the place too.
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Chosen because: {question.location_reason || "it fits what you described"}
          </Typography>
        )}
        <FormControl>
          <RadioGroup value={choice} onChange={(event) => setChoice(event.target.value)}>
            {question.candidates.map((slot, index) => (
              <FormControlLabel
                key={`${slot.start}-${slot.end}`}
                value={String(index + 1)}
                control={<Radio />}
                label={`${slot.start.slice(0, 5)} – ${slot.end.slice(0, 5)}`}
              />
            ))}
            <FormControlLabel value="n" control={<Radio />} label="None of these" />
          </RadioGroup>
        </FormControl>
        <Stack direction="row" sx={{ mt: 2 }}>
          <Button variant="contained" onClick={() => onAnswer(choice)}>
            Answer
          </Button>
        </Stack>
      </CardContent>
    </Card>
  );
}

function LunchGate({
  question,
  onAnswer,
}: {
  question: LunchQuestion;
  onAnswer: (content: string) => void;
}) {
  const [wish, setWish] = useState("");

  return (
    <Card variant="outlined" sx={{ borderColor: "primary.main" }}>
      <CardContent>
        <Typography variant="h6">Lunch?</Typography>
        <Typography color="text.secondary" gutterBottom>
          For {question.headcount}. Say what you feel like, or leave it to the
          kitchen. Still nothing booked.
        </Typography>
        <TextField
          fullWidth
          autoFocus
          label="In your own words"
          placeholder="something vegetarian"
          value={wish}
          onChange={(event) => setWish(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && onAnswer(wish)}
        />
        <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
          <Button variant="contained" onClick={() => onAnswer(wish)}>
            {wish.trim() ? "Order that" : "You choose"}
          </Button>
          <Button onClick={() => onAnswer("no")}>No lunch</Button>
        </Stack>
      </CardContent>
    </Card>
  );
}
