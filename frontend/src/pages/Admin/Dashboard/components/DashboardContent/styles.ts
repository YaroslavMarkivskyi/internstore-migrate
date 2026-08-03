import { Box, Typography, TypographyProps } from '@mui/material';
import { styled } from '@mui/material/styles';

import colors from '@constants/colors';

export const cardStyle = {
  borderRadius: '10px',
  boxShadow: '0px 4px 15px 0px #E0E0E0',
};

export const StyledContainer = styled(Box)`
  padding-top: 40px;
  padding-bottom: 32px;
  width: 100%;
  display: flex;
  flex-direction: column;
`;

export const DashboardTitle = styled(Typography)<TypographyProps>({
  color: colors.dashboard,
  fontFamily: 'Noto Sans',
  fontWeight: 500,
  fontSize: 24,
  lineHeight: '100%',
  marginBottom: 24,
});
