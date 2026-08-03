import { Box, styled, Typography } from '@mui/material';
import { DayPicker } from 'react-day-picker';

import colors from '../../../../constants/colors';
import ButtonAdmin from '../../admin/ButtonAdmin';
import InputFieldAdmin from '../../admin/InputFieldAdmin';

export const Container = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  borderRadius: '10px',
  padding: '10px',
  width: '305px',
});

export const CaptionLabelWrapper = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '100%',
});

export const CaptionLabelText = styled(Typography)({
  fontSize: '14px',
  fontWeight: 600,
  flexGrow: 1,
  textAlign: 'center',
});

export const CustomDatePicker = styled(DayPicker)({
  '&.rdp-root': {
    fontSize: '12px',
    alignSelf: 'center',
    '--rdp-day-height': '22px',
    '--rdp-day-width': '42px',
    '--rdp-day_button-width': '22px',
    '--rdp-day_button-height': '22px',
    '--rdp-accent-background-color': colors.backgroundDisabled,
  },
  '& .rdp-weekday': {
    color: colors.placeholder,
    fontSize: '12px',
    fontWeight: 600,
  },
  '& .rdp-today:not(.rdp-outside)': {
    fontWeight: 800,
    color: colors.secondary.accent100,
  },
  '& .rdp-week': {},
  '& .rdp-day': {
    padding: '0',
  },
  '& .rdp-day_button': {
    margin: 'auto',
    border: 'none',
    borderRadius: '5px',
    color: 'inherit',
  },
  '& .rdp-range_start, .rdp-range_end': {
    height: '22px',
    '& .rdp-day_button': {
      backgroundColor: colors.secondary.accent100,
      color: 'white',
    },
  },
  '& .rdp-selected': {
    fontSize: 'inherit',
    fontWeight: 'inherit',
    '& .rdp-day_button': {
      border: 'none',
    },
  },
  '& .rdp-range_middle': {
    backgroundColor: 'transparent',
    '& .rdp-day_button': {
      backgroundColor: 'var(--rdp-accent-background-color)',
      borderRadius: 0,
      width: '100%',
      border: 'none',
    },
  },
  '& .rdp-month_grid': {
    borderSpacing: '0 10px',
    borderCollapse: 'separate',
  },
});

export const PresetsWrapper = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  columnGap: '2px',
});

export const PresetButton = styled(ButtonAdmin)({
  padding: '10px 6px',
  '&.MuiButton-root': {
    fontSize: '11px',
    fontWeight: 500,
    color: colors.text100,
    '&.Mui-disabled': {
      color: colors.text100,
    },
  },
  '&.Mui-disabled': {
    backgroundColor: colors.backgroundDisabled,
  },
});

export const InputsContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  columnGap: '10px',
  marginTop: '10px',
  marginBottom: '16px',
});

export const DateInput = styled(InputFieldAdmin)({
  '& ::placeholder': {
    textAlign: 'center',
  },
});

export const ButtonsContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  columnGap: '10px',
});
