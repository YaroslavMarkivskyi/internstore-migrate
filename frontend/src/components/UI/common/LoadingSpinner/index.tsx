import { Box, CircularProgress } from '@mui/material';

interface LoadingSpinnerProps {
  size?: number;
  color?:
    | 'primary'
    | 'secondary'
    | 'error'
    | 'info'
    | 'success'
    | 'warning'
    | 'inherit';
}

const LoadingSpinner = ({
  size = 40,
  color = 'primary',
}: LoadingSpinnerProps) => {
  return (
    <Box display="flex" justifyContent="center" alignItems="center">
      <CircularProgress size={size} color={color} />
    </Box>
  );
};

export default LoadingSpinner;
