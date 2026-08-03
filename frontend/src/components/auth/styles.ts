import { IconButton, Typography } from '@mui/material';
import { styled } from '@mui/material/styles';

import colors from '../../constants/colors';

export const ErrorText = styled(Typography)({
  color: colors.error100,
  fontSize: '0.8em',
  textAlign: 'center',
});

export const StyledIconButton = styled(IconButton)({
  position: 'absolute',
  top: 8,
  right: 8,
  zIndex: 1,
});
