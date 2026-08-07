import { Box, List, ListItemButton, styled } from '@mui/material';

// Was a horizontal MUI Tabs strip -- fine for a handful of stocks, but with
// dozens of them (real seed data already has 50+) the row just overflows
// off-screen with no way to reach the rest. A searchable vertical sidebar
// scales the same way Admin/Categories' own CategoriesList already does
// (see that component's styles.ts) -- kept visually consistent with it.
export const SidebarContainer = styled(Box)(() => ({
  width: '260px',
  flexShrink: 0,
  backgroundColor: '#FFFFFF',
  borderRadius: '10px',
  border: '1px solid #E5E5E5',
  boxShadow: '0px 2px 4px rgba(0, 0, 0, 0.05)',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
}));

export const SearchWrapper = styled(Box)(() => ({
  padding: '12px',
  borderBottom: '1px solid #E5E5E5',
}));

export const StyledList = styled(List)(() => ({
  padding: '8px',
  overflowY: 'auto',
  // Roughly 8 rows before scrolling kicks in -- long enough that the
  // common case never needs it, short enough the sidebar can't push the
  // rest of the page down out of view on a stock list this size.
  maxHeight: '420px',
}));

export const StockItem = styled(ListItemButton)(() => ({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  gap: '8px',
  padding: '10px 12px',
  borderRadius: '8px',
  marginBottom: '4px',
  transition: 'background-color 0.15s ease',
  '&.selected': {
    backgroundColor: '#3D318E',
    color: '#FFFFFF',
  },
  '&:not(.selected):hover': {
    backgroundColor: '#F0F0F5',
  },
}));

// flex: 1 + min-width: 0 is what actually makes text-overflow: ellipsis
// work inside a flex row -- without min-width: 0 a flex item won't shrink
// below its content size, so a long name just pushes the (flex-shrink: 0)
// edit icon out of StockItem's clipped bounds instead of truncating.
export const StockName = styled(Box)(() => ({
  flex: 1,
  minWidth: 0,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  fontSize: '14px',
}));

export const EmptyState = styled(Box)(() => ({
  padding: '16px',
  textAlign: 'center',
  color: '#767676',
  fontSize: '14px',
}));
