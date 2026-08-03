import { Menu, styled } from '@mui/material';

export const TriggerWrapper = styled('div')({
  cursor: 'pointer',
});

export const MenuBase = styled(Menu)({
  '& .MuiList-root': {
    padding: '0 0',
    overflowY: 'auto',
    maxHeight: 300,
    minWidth: 200,
  },
  '& .MuiPaper-root': {
    borderRadius: '8px',
    overflow: 'hidden',
    boxShadow: '0px 4px 20px rgba(0, 0, 0, 0.1)',
  },
});
