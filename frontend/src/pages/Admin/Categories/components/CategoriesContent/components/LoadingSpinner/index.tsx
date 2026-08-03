import { memo } from 'react';

import { Box, CircularProgress } from '@mui/material';

/**
 * Simple loading spinner component for when categories are loading
 */
export const LoadingSpinner = memo(() => {
  return (
    <Box
      display="flex"
      justifyContent="center"
      alignItems="center"
      height="400px"
    >
      <CircularProgress />
    </Box>
  );
});
