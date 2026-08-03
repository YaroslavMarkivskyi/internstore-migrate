import { Box, InputLabel, TextField } from '@mui/material';
import { styled } from '@mui/material/styles';

import colors from '../../../../constants/colors';

export const InputWrapper = styled(Box)({
  position: 'relative',
  width: '100%',
  display: 'flex',
  flexDirection: 'column',
  flex: 1,
});

export const Label = styled(InputLabel)(({ theme }) => ({
  color: colors.text100,
  fontWeight: 500,
  fontSize: 14,
  mb: theme.spacing(1),
}));

export const InputBase = styled(TextField)({
  '& .MuiOutlinedInput-root': {
    borderRadius: '10px',
    background: colors.secondary.background,
    border: `1px solid ${colors.border}`,
    fontFamily: 'Noto Sans',
    fontSize: '14px',
  },
  '& .MuiOutlinedInput-notchedOutline': {
    border: 'none',
  },
  '& .MuiOutlinedInput-input': {
    padding: '10px 14px',
  },
});

export const ErrorWrapper = styled(Box)({
  position: 'absolute',
  bottom: 0,
  transform: 'translateY(100%)',
});
