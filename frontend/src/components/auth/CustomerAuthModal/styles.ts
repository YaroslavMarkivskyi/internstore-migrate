import { Popper } from '@mui/material';
import { styled } from '@mui/material/styles';

export const AuthPopper = styled(Popper)(({ theme }) => ({
  zIndex: 1300,
  paddingTop: theme.spacing(2),
}));
