import ClearIcon from '@mui/icons-material/Clear';
import SearchIcon from '@mui/icons-material/Search';
import { Box, styled, Typography } from '@mui/material';

import colors from '../../../../constants/colors';
import ButtonAdmin from '../../admin/ButtonAdmin';
import InputFieldAdmin from '../../admin/InputFieldAdmin';

export const SearchFieldContainer = styled('div')({
  minWidth: '350px',
});

export const Input = styled(InputFieldAdmin)({
  width: '100%',
  '& .MuiOutlinedInput-root': {
    fontSize: '16px',
    width: '100%',
  },
});

export const FoundProductsWrapper = styled(Box)({
  paddingBottom: '20px',
});

export const ItemRowWrapper = styled(Box)({
  cursor: 'pointer',
  display: 'flex',
  flexDirection: 'row',
  alignItems: 'center',
  justifyContent: 'flex-start',
  columnGap: '40px',
  width: '100%',
  padding: '0 20px',
  '&:hover': {
    backgroundColor: colors.backgroundDisabled,
  },
});

export const ItemsWrapper = styled(Box)({
  marginBottom: '10px',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'flex-start',
});

export const ProductImageWrapper = styled(Box)({
  padding: '5px 0',
  display: 'flex',
});

export const ProductImage = styled('img')({
  width: '65px',
  height: '65px',
  objectFit: 'contain',
});

export const ProductTitle = styled(Typography)({
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
});

export const ProductCount = styled(Typography)({
  marginLeft: '20px',
  fontSize: '12px',
  color: colors.placeholder,
});

export const ButtonWrapper = styled(Box)({
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  marginTop: '10px',
  width: '100%',
});

export const ShowAllButton = styled(ButtonAdmin)({
  '&.MuiButton-text': {
    fontWeight: 600,
  },
});

export const NotFoundText = styled(Typography)({
  fontSize: '14px',
  color: colors.placeholder,
  margin: '30px auto',
  textAlign: 'center',
});

export const HistoryWrapper = styled(Box)({
  padding: '10px',
  paddingTop: '15px',
});

export const HistoryHeaderWrapper = styled(Box)({
  display: 'flex',
  flexDirection: 'row',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '0 15px',
});

export const ClearAllButton = styled(ButtonAdmin)({
  padding: 0,
  '&.MuiButton-text': {
    fontWeight: 600,
    fontSize: '12px',
    color: colors.secondary.accent300,
  },
  '&.MuiButton-text:hover': {
    backgroundColor: 'transparent',
    color: '#221B52',
  },
});

export const HistoryHeader = styled(Typography)({
  fontWeight: 600,
  fontSize: '12px',
});

export const HistoryItemsWrapper = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'flex-start',
  marginTop: '18px',
});

export const HistoryItem = styled(Box)({
  width: '100%',
  display: 'flex',
  justifyContent: 'flex-start',
  alignItems: 'center',
  padding: '10px 19px 10px 27px',
  cursor: 'pointer',
  '&:hover': {
    backgroundColor: colors.backgroundDisabled,
  },
});

export const HistorySearchIcon = styled(SearchIcon)({
  marginRight: '12px',
  fill: colors.placeholder,
});

export const HistoryDeleteIcon = styled(ClearIcon)({
  marginLeft: 'auto',
  fill: colors.placeholder,
});

export const HistoryText = styled(Typography)({
  fontSize: '12px',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
});
