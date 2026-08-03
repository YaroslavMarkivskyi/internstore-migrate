import { Box, keyframes, styled } from '@mui/material';

const fadeIn = keyframes`
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
`;

export const InputContainer = styled(Box)(() => ({
  display: 'flex',
  flexDirection: 'column',
  background: '#ffffff',
  borderRadius: '10px',
  padding: '5px',
  boxShadow: '0 4px 16px rgba(0,0,0,0.1)',
  width: '260px',
  position: 'absolute',
  top: '100%',
  right: 'auto',
  marginTop: '5px',
  zIndex: 10,
  animation: `${fadeIn} 0.2s ease-out`,
  border: 'none',
}));
