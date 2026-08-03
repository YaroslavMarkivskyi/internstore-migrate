import { SxProps, Theme } from '@mui/material';

import colors from '@constants/colors';

export const styles = {
  container: {
    pb: 4,
    width: '100%',
    marginTop: '44px',
  } as SxProps<Theme>,

  loadingContainer: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: '50vh',
  } as SxProps<Theme>,

  errorContainer: {
    py: 8,
  } as SxProps<Theme>,

  errorContent: {
    textAlign: 'center',
  } as SxProps<Theme>,

  errorButton: {
    mt: 2,
  } as SxProps<Theme>,

  paper: {
    p: 6,
    mb: 4,
    borderRadius: 2,
    width: '100%',
  } as SxProps<Theme>,

  productLayout: {
    display: 'flex',
    flexDirection: { xs: 'column', md: 'row' },
    gap: 4,
  } as SxProps<Theme>,

  imageContainer: {
    flex: 1,
  } as SxProps<Theme>,

  imageBox: {
    height: 400,
    width: '100%',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: 2,
    overflow: 'hidden',
  } as SxProps<Theme>,

  image: {
    maxHeight: '100%',
    maxWidth: '100%',
    objectFit: 'contain' as const,
  },

  detailsContainer: {
    flex: 1,
  } as SxProps<Theme>,

  title: {
    fontSize: '18px',
  } as SxProps<Theme>,

  priceAndButtonRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '20px',
    mb: '25px',
    mt: '25px',
  } as SxProps<Theme>,

  price: {
    fontWeight: 500,
    mb: 0,
    fontSize: '24px',
    color: '#212121',
  } as SxProps<Theme>,

  addToCartContainer: {
    mt: 0,
  } as SxProps<Theme>,

  addToCartButton: {
    minWidth: 'auto',
    px: 3,
    py: 1,
  } as SxProps<Theme>,

  addToCartButtonWithColors: {
    minWidth: 'auto',
    px: 3,
    py: 1,
    backgroundColor: '#3D318E',
    '&:hover': {
      backgroundColor: '#504599',
    },
    '&.MuiButton-root.Mui-disabled': {
      color: colors.secondary.accent100,
    },
  } as SxProps<Theme>,
};
