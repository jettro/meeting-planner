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
import PlanPage from "./pages/PlanPage";
import PlatformPage from "./pages/PlatformPage";
import TracePage from "./pages/TracePage";
import { TeamProvider } from "./TeamContext";

const theme = createTheme({ palette: { primary: { main: "#2d6a4f" } } });
const client = new QueryClient();

const TABS = [
  { path: "/", label: "Platform" },
  { path: "/plan", label: "Plan a meeting" },
  { path: "/trace", label: "Trace" },
];

function Shell() {
  const { pathname } = useLocation();
  const current = TABS.some((tab) => tab.path === pathname) ? pathname : "/";

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
          <Route path="/trace" element={<TracePage />} />
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
