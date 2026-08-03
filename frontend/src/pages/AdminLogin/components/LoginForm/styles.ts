import { styled } from '@mui/material/styles';

export const FormWrapper = styled('div')({
  display: 'flex',
  flexDirection: 'column',
  width: '330px',
  justifyContent: 'center',
  alignItems: 'center',
  gap: '20px',
  padding: '20px',
});

export const FormHeader = styled('h2')({
  fontFamily: 'Noto Sans',
  fontSize: '16px',
  fontWeight: '500',
  color: '#121212',
  lineHeight: '100%',
  letterSpacing: '0',
});

export const FormControlStyled = styled('form')({
  display: 'flex',
  flexDirection: 'column',
  width: '290px',
  justifyContent: 'center',
  alignItems: 'center',
  gap: '30px',
});
