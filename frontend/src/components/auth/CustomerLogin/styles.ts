import { Stack, Typography } from '@mui/material';
import { styled } from '@mui/material/styles';

export const LoginContainer = styled('form')({
  width: '300px',
  padding: '1em',
  borderRadius: '5px',
  boxShadow: '0px 4px 15px #E0E0E0',
  position: 'relative',
});

export const LoginTitle = styled(Typography)({
  textAlign: 'center',
  marginBottom: '20px',
});

export const InputsContainer = styled(Stack)({
  spacing: '30px',
  marginBottom: '30px',
});

export const ButtonsContainer = styled(Stack)({
  spacing: '20px',
});
