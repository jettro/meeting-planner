import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Stack,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { api, type ServiceHealth } from "../api/client";

const COLOURS: Record<ServiceHealth["status"], "success" | "warning" | "error"> = {
  up: "success",
  degraded: "warning",
  unreachable: "error",
};

/**
 * The first screen, because it answers the first question.
 *
 * "Degraded" and "unreachable" are kept apart deliberately: a service that
 * answered 503 has a broken database, one that did not answer at all has a
 * broken network or no process. Showing both as "down" throws away the only
 * clue in the room.
 */
export default function PlatformPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["platform-health"],
    queryFn: api.platformHealth,
    refetchInterval: 10_000,
  });

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Platform
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        The agents can only book what the services can serve. This is the three of
        them, asked at once.
      </Typography>

      {isLoading && <CircularProgress />}
      {error && (
        <Alert severity="error">
          The server did not answer: {String((error as Error).message)}
        </Alert>
      )}

      {data && (
        <Stack spacing={2}>
          <Alert severity={data.status === "up" ? "success" : "warning"}>
            {data.status === "up"
              ? "Everything is up. A meeting can be planned."
              : "Something is wrong. Planning will fail part-way through."}
          </Alert>
          {data.services.map((service) => (
            <Card key={service.name} variant="outlined">
              <CardContent>
                <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
                  <Chip label={service.status} color={COLOURS[service.status]} size="small" />
                  <Typography sx={{ flexGrow: 1 }}>{service.name}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {service.url}
                  </Typography>
                </Stack>
                {service.detail && (
                  <Typography variant="body2" color="error" sx={{ mt: 1 }}>
                    {service.detail}
                  </Typography>
                )}
              </CardContent>
            </Card>
          ))}
        </Stack>
      )}
    </Box>
  );
}
