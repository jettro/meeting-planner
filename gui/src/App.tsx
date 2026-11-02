import {
  AppBar,
  Box,
  Button,
  CircularProgress,
  Container,
  CssBaseline,
  Tab,
  Tabs,
  ThemeProvider,
  Toolbar,
  Typography,
  createTheme,
} from "@mui/material";
import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import ChatPage from "./pages/ChatPage";
import LoginPage from "./pages/LoginPage";
import MeetingsPage from "./pages/MeetingsPage";
import MemoryPage from "./pages/MemoryPage";
import PlanPage from "./pages/PlanPage";
import PlatformPage from "./pages/PlatformPage";
import TracePage from "./pages/TracePage";
import { useSession } from "./session";
import { SessionProvider } from "./SessionContext";
import { TeamProvider } from "./TeamContext";

const theme = createTheme({ palette: { primary: { main: "#2d6a4f" } } });
const client = new QueryClient();

const TABS = [
  { path: "/", label: "Platform" },
  { path: "/plan", label: "Plan a meeting" },
  { path: "/chat", label: "Talk to the planner" },
  { path: "/meetings", label: "Meetings" },
  { path: "/trace", label: "Trace" },
  { path: "/memory", label: "Memory" },
];

/** Who is logged in, and the way out - on the right of the app bar. */
function UserBar() {
  const session = useSession();
  if (!session.user) return null;
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
      <Typography variant="body2">{session.user.name}</Typography>
      {session.canLogOut && (
        <Button color="inherit" size="small" onClick={() => void session.logout()}>
          Log out
        </Button>
      )}
    </Box>
  );
}

/**
 * The tabs, for somebody who is logged in - otherwise the login page.
 *
 * The team being watched and every cached answer belong to one person, so a
 * change of person starts both afresh: the team provider is keyed on who it is,
 * and the query cache is emptied.
 */
function Gate() {
  const { user } = useSession();
  const queries = useQueryClient();
  const who = user?.user_id ?? null;

  useEffect(() => {
    queries.clear();
  }, [who, queries]);

  if (user === undefined) return <CircularProgress sx={{ m: 4 }} />;
  if (user === null) {
    return (
      <Box>
        <AppBar position="static">
          <Toolbar>
            <Typography variant="h6">Meeting planner</Typography>
          </Toolbar>
        </AppBar>
        <Container sx={{ py: 4 }}>
          <LoginPage />
        </Container>
      </Box>
    );
  }
  return (
    <TeamProvider key={who}>
      <Shell />
    </TeamProvider>
  );
}

function Shell() {
  const { pathname } = useLocation();
  // `/trace/<team>` is still the Trace tab, so a path segment below a tab
  // counts as that tab - but only on a segment boundary, so `/plan` and a
  // longer path that merely starts with it are never confused.
  const current =
    TABS.map((tab) => tab.path).find(
      (path) => path !== "/" && (pathname === path || pathname.startsWith(`${path}/`)),
    ) ?? "/";

  return (
    <Box>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Meeting planner
          </Typography>
          <UserBar />
        </Toolbar>
        <Tabs value={current} textColor="inherit" indicatorColor="secondary">
          {TABS.map((tab) => (
            <Tab key={tab.path} value={tab.path} label={tab.label} component={Link} to={tab.path} />
          ))}
        </Tabs>
      </AppBar>
      <Container sx={{ py: 4 }}>
        <Routes>
          <Route path="/" element={<PlatformPage />} />
          <Route path="/plan" element={<PlanPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/meetings" element={<MeetingsPage />} />
          <Route path="/trace" element={<TracePage />} />
          <Route path="/trace/:teamId" element={<TracePage />} />
          <Route path="/memory" element={<MemoryPage />} />
        </Routes>
      </Container>
    </Box>
  );
}

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <QueryClientProvider client={client}>
        {/* The plan being watched lives in memory, not in the URL: a reload
            would lose the stream anyway, and a shareable link to a team that
            is waiting for *this* browser to answer a question is a trap. */}
        <MemoryRouter>
          <SessionProvider>
            <Gate />
          </SessionProvider>
        </MemoryRouter>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
