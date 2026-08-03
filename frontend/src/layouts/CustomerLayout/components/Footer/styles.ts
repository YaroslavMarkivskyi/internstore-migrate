import EmailOutlinedIcon from '@mui/icons-material/EmailOutlined';
import { Box, styled, Typography } from '@mui/material';

import colors from '@constants/colors';

export const FooterContainer = styled(Box)({
  backgroundColor: 'white',
  marginTop: '40px',
});

export const FooterWrapper = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  paddingTop: '32px',
  paddingBottom: '32px',
});

export const FooterTypography = styled(Typography)({
  fontWight: 500,
  fontSize: '16px',
});

export const ConnectWithUsContainer = styled('a')({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  columnGap: '24px',
  textDecoration: 'none',
  color: 'inherit',
});

export const ConnectWithUsIcon = styled(EmailOutlinedIcon)({
  fill: colors.secondary.accent100,
});
