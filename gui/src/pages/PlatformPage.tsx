import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Link,
  Stack,
  Typography,
} from "@mui/material";
import { useQueries, useQuery } from "@tanstack/react-query";
import { api, type ServiceHealth, type ServiceInfo } from "../api/client";

const COLOURS: Record<ServiceHealth["status"], "success" | "warning" | "error"> = {
  up: "success",
  degraded: "warning",
  unreachable: "error",
};

const EVERY = 10_000;

/**
 * The first screen, because it answers the first question.
 *
 * "Degraded" and "unreachable" are kept apart deliberately: a service that
 * answered 503 has a broken database, one that did not answer at all has a
 * broken network or no process. Showing both as "down" throws away the only
 * clue in the room.
 *
 * The page asks for the list of services first - an answer that probes
 * nothing, so the frame is there at once - and then asks each service on its
 * own. A dot turns as soon as its own answer arrives; a service that hangs
 * holds up its own card and nothing else.
 */
export default function PlatformPage() {
  const services = useQuery({
    queryKey: ["platform-services"],
    queryFn: api.platformServices,
    staleTime: Infinity,
  });

  const checks = useQueries({
    queries: (services.data ?? []).map((service) => ({
      queryKey: ["platform-health", service.name],
      queryFn: () => api.serviceHealth(service.name),
      refetchInterval: EVERY,
    })),
  });

  const answered = checks.filter((check) => check.data).length;
  const total = services.data?.length ?? 0;
  const allUp = total > 0 && checks.every((check) => check.data?.status === "up");
  const anyDown = checks.some((check) => check.data && check.data.status !== "up") ||
    checks.some((check) => check.error);

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Platform
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        The agents can only book what the services can serve. This is the three of
        them, each asked on its own.
      </Typography>

      {services.error && (
        <Alert severity="error">
          The server did not answer: {String((services.error as Error).message)}
        </Alert>
      )}

      <Stack spacing={2}>
        {services.isLoading ? (
          <CircularProgress size={24} />
        ) : allUp ? (
          <Alert severity="success">Everything is up. A meeting can be planned.</Alert>
        ) : anyDown ? (
          <Alert severity="warning">
            Something is wrong. Planning will fail part-way through.
          </Alert>
        ) : (
          total > 0 && (
            <Alert severity="info">
              Asking the services… {answered} of {total} answered.
            </Alert>
          )
        )}

        {(services.data ?? []).map((service, index) => (
          <ServiceCard
            key={service.name}
            service={service}
            health={checks[index]?.data}
            error={checks[index]?.error as Error | null | undefined}
          />
        ))}
      </Stack>
    </Box>
  );
}

function ServiceCard({
  service,
  health,
  error,
}: {
  service: ServiceInfo;
  health: ServiceHealth | undefined;
  error: Error | null | undefined;
}) {
  const detail = health?.detail ?? (error ? `The server did not answer: ${error.message}` : null);
  return (
    <Card variant="outlined">
      <CardContent>
        <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
          {health ? (
            <Chip label={health.status} color={COLOURS[health.status]} size="small" />
          ) : error ? (
            <Chip label="unknown" color="error" variant="outlined" size="small" />
          ) : (
            <Chip
              label="checking"
              size="small"
              variant="outlined"
              icon={<CircularProgress size={12} />}
            />
          )}
          <Typography sx={{ flexGrow: 1 }}>{service.name}</Typography>
          <Link
            href={service.link}
            target="_blank"
            rel="noopener noreferrer"
            variant="body2"
          >
            {service.link}
          </Link>
        </Stack>
        {detail && (
          <Typography variant="body2" color="error" sx={{ mt: 1 }}>
            {detail}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}
