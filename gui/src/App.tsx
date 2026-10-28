import {
  AppBar,
  Box,
  Container,
  CssBaseline,
  Tab,
  Tabs,
  ThemeProvider,
  Toolbar,
  Typography,
  createTheme,
} from "@mui/material";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Link, MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import ChatPage from "./pages/ChatPage";
import MeetingsPage from "./pages/MeetingsPage";
import PlanPage from "./pages/PlanPage";
import PlatformPage from "./pages/PlatformPage";
import TracePage from "./pages/TracePage";
import { TeamProvider } from "./TeamContext";

const theme = createTheme({ palette: { primary: { main: "#2d6a4f" } } });
const client = new QueryClient();

const TABS = [
  { path: "/", label: "Platform" },
  { path: "/plan", label: "Plan a meeting" },
  { path: "/chat", label: "Talk to the planner" },
  { path: "/meetings", label: "Meetings" },
  { path: "/trace", label: "Trace" },
];

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
          <Typography variant="h6">Meeting planner</Typography>
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
          <TeamProvider>
            <Shell />
          </TeamProvider>
        </MemoryRouter>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
