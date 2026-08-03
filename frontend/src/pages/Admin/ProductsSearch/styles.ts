import { Typography, TypographyProps } from '@mui/material';
import { styled } from '@mui/material/styles';

export const SearchTitle = styled(Typography)<TypographyProps>(({ theme }) => ({
  fontWeight: 500,
  marginRight: theme.spacing(2),
}));

export const NotFoundTitle = styled(Typography)<TypographyProps>(
  ({ theme }) => ({
    fontWeight: 500,
    marginTop: theme.spacing(2),
  })
);
