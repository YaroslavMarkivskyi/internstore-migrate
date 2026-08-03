import { styled } from '@mui/material/styles';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';

export const StyledTabs = styled(Tabs)(() => ({
  backgroundColor: '#E3E3EB',
  borderRadius: '10px 10px 0 0',
  width: 'auto',
  display: 'inline-flex',
  minHeight: '40px',
  '& .MuiTabs-indicator': {
    display: 'none',
  },
}));

export const StyledTab = styled(Tab)(() => ({
  textTransform: 'none',
  fontWeight: 'Noto Sans',
  fontSize: '16px',
  color: '#212121',
  borderRadius: '10px 10px 0 0',
  minHeight: '46px',
  '&.Mui-selected': {
    backgroundColor: '#FFFFFF',
    color: '#212121',
    fontWeight: 'bold',
    boxShadow: '0px 1px 3px rgba(0, 0, 0, 0.1)',
  },
}));
