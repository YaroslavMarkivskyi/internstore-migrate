import { Box, styled, Typography } from '@mui/material';

import colors from '@constants/colors';

export const Wrapper = styled(Box)({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'flex-start',
  alignItems: 'flex-start',
  paddingBottom: '5px', // So shadow won't overflow
});

export const Title = styled(Typography)({
  alignSelf: 'flex-start',
  marginBottom: '20px',
});

export const ListContainer = styled(Box)({
  flexGrow: 1,
  width: '100%',
  display: 'flex',
  flexDirection: 'column',
  gap: '30px',
});

export const NothingFoundText = styled(Typography)({
  color: colors.textDisabled100,
  marginTop: '20px',
  alignSelf: 'center',
});
