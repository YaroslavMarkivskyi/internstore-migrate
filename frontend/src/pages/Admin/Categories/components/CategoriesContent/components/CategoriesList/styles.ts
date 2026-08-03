import { Box, List, ListItem, styled } from '@mui/material';

export const CategoryListContainer = styled(Box)(() => ({
  width: '250px',
  backgroundColor: '#FFFFFF',
  borderRadius: '10px',
  padding: '16px',
  height: 'fit-content',
  border: '1px solid #E5E5E5',
  boxShadow: '0px 2px 4px rgba(0, 0, 0, 0.05)',
}));

export const StyledList = styled(List)(() => ({
  padding: 0,
  width: '100%',
}));

export const CategoryItem = styled(ListItem)(() => ({
  padding: '12px 16px',
  borderRadius: '4px',
  marginBottom: '4px',
  cursor: 'pointer',
  '&:hover:not(.selected)': {
    backgroundColor: '#f0f0f0',
  },
  transition: 'all 0.2s ease',
}));

export const CategoryCount = styled(Box)(() => ({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  minWidth: '24px',
  height: '24px',
  padding: '0 8px',
  borderRadius: '12px',
  fontSize: '12px',
  fontWeight: 600,
}));
