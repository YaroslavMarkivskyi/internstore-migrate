import { styled } from '@mui/material';

export const Container = styled('div')(({ theme }) => ({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  height: '100vh',
  backgroundColor: theme.palette.background.default,
}));

export const LogoStatic = styled('div')({
  position: 'absolute',
  top: '20px',
  left: '20px',
});
