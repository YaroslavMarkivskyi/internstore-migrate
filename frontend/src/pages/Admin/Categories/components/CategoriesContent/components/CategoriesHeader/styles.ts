import { Box, styled, Typography } from '@mui/material';

export const HeaderContainer = styled(Box)(() => ({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  width: '100%',
  marginBottom: '24px',
  position: 'relative',
}));

export const HeaderTitle = styled(Typography)(() => ({
  fontSize: '24px',
  fontWeight: 600,
  color: '#10045C',
  fontFamily: '"Noto Sans", sans-serif',
}));

export const ButtonContainer = styled(Box)(() => ({
  display: 'flex',
  justifyContent: 'flex-end',
  position: 'relative',
}));
