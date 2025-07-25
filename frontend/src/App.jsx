import React from 'react';
import { BrowserRouter as Router } from 'react-router-dom';
import { ThemeProvider, CssBaseline, Box } from '@mui/material';
import { QueryClient, QueryClientProvider } from 'react-query';
import { useThemeToggle } from './hooks/useThemeToggle';
import Layout from './components/Layout/Layout';
import AppRoutes from './routes';

const queryClient = new QueryClient();

function App() {
  const { theme, toggleTheme } = useThemeToggle();

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Box
          sx={{
            minHeight: '100vh',
            width: '100vw',
            background: (theme) =>
              theme.palette.mode === 'dark'
                ? 'linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #16213e 100%)'
                : 'linear-gradient(135deg, #fafbfc 0%, #f6f8fa 50%, #f0f2f5 100%)',
            backgroundAttachment: 'fixed',
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
          }}
        />
        <Box
          sx={{
            position: 'relative',
            minHeight: '100vh',
            width: '100vw',
          }}
        >
          {/* Background decoration */}
          <Box
            sx={{
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: (theme) =>
                theme.palette.mode === 'dark'
                  ? 'radial-gradient(circle at 80% 20%, rgba(139, 92, 246, 0.1) 0%, transparent 50%), radial-gradient(circle at 20% 80%, rgba(6, 182, 212, 0.1) 0%, transparent 50%)'
                  : 'radial-gradient(circle at 80% 20%, rgba(139, 92, 246, 0.08) 0%, transparent 50%), radial-gradient(circle at 20% 80%, rgba(6, 182, 212, 0.08) 0%, transparent 50%)',
              pointerEvents: 'none',
              zIndex: 0,
            }}
          />
          <Router>
            <Layout toggleTheme={toggleTheme}>
              <AppRoutes />
            </Layout>
          </Router>
        </Box>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
