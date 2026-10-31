import {
  Alert,
  Avatar,
  Box,
  Card,
  CardActionArea,
  CardContent,
  CircularProgress,
  Grid,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { auth } from "../api/client";
import { useSession } from "../session";

function initials(name: string): string {
  return name
    .split(" ")
    .filter((part) => part[0] === part[0]?.toUpperCase())
    .map((part) => part[0])
    .slice(0, 2)
    .join("");
}

/**
 * Pick who you are (design_auth.md A2, A3).
 *
 * Everybody the meeting service knows may log in, and nobody needs a password.
 * The page says so in as many words: this demonstrates *users* - your own
 * meetings, later your own memory - not security. Everything after this page
 * treats the person as authenticated, so a real identity provider replaces
 * this page and nothing else (A8).
 */
export default function LoginPage() {
  const session = useSession();
  const [error, setError] = useState<string | null>(null);
  const people = useQuery({ queryKey: ["people"], queryFn: auth.people });

  const choose = async (email: string) => {
    setError(null);
    try {
      await session.loginAs(email);
    } catch (failure) {
      setError(String((failure as Error).message ?? failure));
    }
  };

  return (
    <Box sx={{ maxWidth: 760, mx: "auto" }}>
      <Typography variant="h5" gutterBottom>
        Who are you?
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        Pick one of the people the meeting service keeps an agenda for. You will see the meetings
        you arranged, and nobody else's.
      </Typography>
      <Alert severity="info" sx={{ mb: 3 }}>
        This is a demo login: there is no password, so anyone can be anyone.
      </Alert>

      {people.isPending && <CircularProgress />}
      {people.isError && (
        <Alert severity="error">
          The list of people could not be read - is the meeting service up? ({String(people.error.message)})
        </Alert>
      )}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={2}>
        {people.data?.map((person) => (
          <Grid key={person.email} size={{ xs: 12, sm: 6, md: 4 }}>
            <Card variant="outlined">
              <CardActionArea onClick={() => void choose(person.email)}>
                <CardContent sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                  <Avatar sx={{ bgcolor: "primary.main" }}>{initials(person.name)}</Avatar>
                  <Box sx={{ minWidth: 0 }}>
                    <Typography noWrap>{person.name}</Typography>
                    <Typography variant="body2" color="text.secondary" noWrap>
                      {person.email}
                    </Typography>
                  </Box>
                </CardContent>
              </CardActionArea>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
