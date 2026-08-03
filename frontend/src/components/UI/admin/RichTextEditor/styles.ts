import { Box, IconButton, Stack } from '@mui/material';
import { styled } from '@mui/material/styles';

export const Wrapper = styled(Box)({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
});

export const EditArea = styled(Box)({
  background: '#FAFAFA',
  border: '1px solid #E0E0E0',
  borderRadius: 10,
  borderBottom: 'none',
  borderBottomRightRadius: 0,
  borderBottomLeftRadius: 0,
  flex: 1,
  display: 'flex',
  overflowY: 'auto',
  position: 'relative',
});

export const ControlsContainer = styled(Stack)({
  display: 'flex',
  flexDirection: 'row',
  alignItems: 'center',
  justifyContent: 'space-between',
  backgroundColor: '#FFFFFF',
  border: '1px solid #E0E0E0',
  borderBottomRightRadius: 10,
  borderBottomLeftRadius: 10,
});

export const IconButtonContainer = styled(IconButton)({
  padding: '16px 0',
  flex: 1,
  borderRadius: 0,
  color: '#686767',
});
