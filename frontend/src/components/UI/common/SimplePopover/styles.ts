import { Menu, styled } from '@mui/material';

export const TriggerWrapper = styled('div')({
  cursor: 'pointer',
});

export const MenuBase = styled(Menu)({
  '& .MuiList-root': {
    padding: 0,
    overflowY: 'auto',
  },
  '& .MuiPaper-root': {
    borderRadius: '5px',
    overflow: 'hidden',
  },
});
