import { Box, CircularProgress } from '@mui/material';

export const LoadingIndicator = () => (
  <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
    <CircularProgress />
  </Box>
);
