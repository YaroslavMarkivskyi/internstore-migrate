import ArrowForwardIosIcon from '@mui/icons-material/ArrowForwardIos';
import { Box, Stack, Typography } from '@mui/material';
import { styled } from '@mui/material/styles';

import ButtonAdmin from '../UI/admin/ButtonAdmin';

import colors from '../../constants/colors';

export const FormContainer = styled('form')(({ theme }) => ({
  backgroundColor: theme.palette.background.default,
  boxShadow: `0px 4px 15px ${colors.border}`,
  borderRadius: 10,
  padding: theme.spacing(3),
  display: 'flex',
  flexDirection: 'column',
  rowGap: theme.spacing(5),
  flex: 1,
  maxWidth: 1163,
}));

export const FormColumnsWrapper = styled('div')(({ theme }) => ({
  display: 'flex',
  justifyContent: 'space-between',
  columnGap: theme.spacing(5),
}));

export const FormColumnContainer = styled(Stack)(({ theme }) => ({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  rowGap: theme.spacing(3.75),
}));

export const ButtonsContainer = styled(Stack)(({ theme }) => ({
  display: 'flex',
  flexDirection: 'row',
  columnGap: theme.spacing(2.5),
}));

export const UploadImageButton = styled(ButtonAdmin)({
  boxShadow: 'none',
  '&.MuiButton-contained': {
    border: colors.backgroundDisabled,
    backgroundColor: colors.backgroundDisabled,
    color: colors.secondary.accent100,
    fontSize: '12px',
    '&.Mui-disabled': {
      color: colors.placeholder,
    },
  },
  '&.MuiButton-outlined': {
    border: `1px solid ${colors.secondary.accent100}`,
    backgroundColor: 'transparent',
    color: colors.secondary.accent100,
    fontSize: '12px',
    '&:hover': {
      backgroundColor: colors.secondary.accent100,
      color: colors.primary.background,
    },
    '&.Mui-disabled': {
      color: colors.placeholder,
      borderColor: colors.placeholder,
    },
  },
});

export const UploadImageWrapper = styled(Box)({
  position: 'relative',
  width: '100%',
});

export const UploadImageError = styled(Typography)({
  position: 'absolute',
  bottom: -8,
  transform: 'translateY(100%)',
});

export const FormWrapper = styled(Box)({
  flex: 1,
  maxWidth: 1163,
});

export const PathContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'flex-start',
  marginBottom: '30px',
  marginTop: '36px',
  columnGap: '8px',
});

export const PathTextParent = styled(Typography)({
  fontWeight: 500,
  fontSize: '16px',
  color: colors.dashboard,
});

export const PathTextDetails = styled(PathTextParent)({
  color: colors.text300,
});

export const PathIcon = styled(ArrowForwardIosIcon)({
  fontSize: '13px',
});
