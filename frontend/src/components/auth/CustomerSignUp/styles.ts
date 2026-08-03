import { Box, Typography } from '@mui/material';
import { styled } from '@mui/material/styles';

export const SignUpContainer = styled('form')(() => ({
  width: '300px',
  padding: '1em',
  borderRadius: '5px',
  boxShadow: '0px 4px 15px #E0E0E0',
  position: 'relative',
}));

export const SignUpTitle = styled(Typography)({
  textAlign: 'center',
  marginBottom: '20px',
});

export const RuleTag = styled(Box, {
  shouldForwardProp: prop => prop !== 'valid',
})<{ valid?: boolean }>(({ valid }) => ({
  backgroundColor: valid ? '#C9DCC9' : '#E0E0E0',
  borderRadius: '20px',
}));

export const RuleText = styled(Typography)({
  fontSize: 12,
  color: 'text.secondary',
  padding: '4px 6px',
});
