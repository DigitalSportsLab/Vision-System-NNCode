import React from 'react';
import { Box } from '@mui/material';
import Sidebar from './Sidebar';

const Layout = ({ children, toggleTheme }) => {
  return (
    <Box
      sx={{
        display: 'flex',
        minHeight: '100vh',
        width: '100vw',
        overflow: 'hidden',
      }}
    >
      <Sidebar toggleTheme={toggleTheme} />
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          height: '100vh',
          overflow: 'auto',
          position: 'relative',
          backgroundColor: 'transparent',
        }}
      >
        {children}
      </Box>
    </Box>
  );
};

export default Layout;
