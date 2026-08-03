import {
  MenuItem,
  Popover,
  Select,
  styled,
  TextField,
  Typography,
} from '@mui/material';

import colors from '@constants/colors';

export const PopupContainer = styled(Popover)(({ theme }) => ({
  '& .MuiPaper-root': {
    borderRadius: '10px',
    boxShadow: '0px 4px 15px #E0E0E0',
    padding: theme.spacing(3),
    minWidth: 300,
    maxWidth: 600,
  },
}));

export const PutInStockTitle = styled(Typography)(({ theme }) => ({
  fontWeight: 500,
  fontSize: '16px',
  textAlign: 'center',
  marginBottom: theme.spacing(2),
}));

export const InputField = styled(TextField)(() => ({
  minWidth: 160,
  '& .MuiOutlinedInput-root': {
    borderRadius: 10,
    '& fieldset': {
      borderColor: '#E0E0E0',
    },
  },
}));

export const ChooseField = styled(Select)(() => ({
  minWidth: 160,
  borderRadius: 10,
  '& .MuiSelect-select': {
    borderRadius: 10,
    padding: '10px 14px',
  },
  '& fieldset': {
    borderColor: '#E0E0E0',
  },
}));

export const ChooseFieldMenuItem = styled(MenuItem)(() => ({
  '&.Mui-selected': {
    backgroundColor: colors.secondary.accent100,
    color: 'white',
    '& .MuiTypography-root': {
      color: 'white',
    },
    '&:hover': {
      backgroundColor: colors.secondary.accent100,
      color: 'white',
    },
    '& .Mui-disabled': {
      color: 'white',
    },
  },
  '&:hover': {
    backgroundColor: colors.secondary.accent100,
    color: 'white',
  },
  padding: '15px 10px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
}));
