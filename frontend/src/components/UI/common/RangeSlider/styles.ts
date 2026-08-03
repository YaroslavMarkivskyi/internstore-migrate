import {
  Box,
  BoxProps,
  Slider,
  SliderProps,
  Typography,
  TypographyProps,
} from '@mui/material';
import { styled } from '@mui/material/styles';

import colors from '../../../../constants/colors';

// Container for the entire slider component with horizontal layout
export const SliderContainer = styled(Box)<BoxProps>({
  width: '100%',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '8px 0',
});

// Box containing the value display at both ends
export const ValueDisplay = styled(Box)<BoxProps>({
  background: 'white',
  border: `1px solid ${colors.border}`,
  borderRadius: '4px',
  padding: '8px 16px',
  minWidth: '60px',
  textAlign: 'center',
  display: 'inline-block',
  flexShrink: 0,
});

// Wrapper for the slider to handle flex spacing
export const SliderWrapper = styled(Box)<BoxProps>({
  flex: 1,
  margin: '0 16px',
});

// Text for the min/max values
export const ValueText = styled(Typography)<TypographyProps>({
  fontWeight: 500,
  fontSize: '14px',
  color: colors.text300,
});

// Custom Slider with yellow track and indigo thumbs
export const StyledSlider = styled(Slider)<SliderProps>({
  height: 4,
  color: colors.warning100, // Yellow color from the image
  '& .MuiSlider-rail': {
    backgroundColor: colors.text1000,
    opacity: 1,
  },
  '& .MuiSlider-thumb': {
    height: 16,
    width: 16,
    backgroundColor: '#fff',
    border: `2px solid ${colors.secondary.accent100}`, // Secondary accent color
    '&:focus, &:hover, &.Mui-active, &.Mui-focusVisible': {
      boxShadow: '0px 0px 0px 8px rgba(61, 49, 142, 0.16)',
    },
  },
  '& .MuiSlider-valueLabel': {
    display: 'none', // Hide the default value labels
  },
});
