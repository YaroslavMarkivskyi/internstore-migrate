import { Box, styled } from '@mui/material';

// ------------------------------------------------------------
// DASHBOARD TILES STYLING
// ------------------------------------------------------------

// Container and layout styles
export const TilesContainer = styled(Box)({
  margin: '0 0 30px 0',
  width: '100%',
  padding: 0,
  boxSizing: 'border-box',
});

export const GridContainer = styled(Box)(({ theme }) => ({
  display: 'grid',
  gridTemplateColumns: '1fr',
  gap: theme.spacing(3),
  width: '100%',
  margin: 0,
  padding: 0,
  boxSizing: 'border-box',
  [theme.breakpoints.up('md')]: {
    gridTemplateColumns: '2fr 1fr',
  },
}));

// Left section styling
export const LeftSection = styled(Box)(({ theme }) => ({
  display: 'flex',
  flexDirection: 'column',
  gap: theme.spacing(3),
}));

export const TopCardsRow = styled(Box)(({ theme }) => ({
  display: 'grid',
  gridTemplateColumns: '1fr',
  gap: theme.spacing(3),
  flex: 1,
  [theme.breakpoints.up('sm')]: {
    gridTemplateColumns: 'repeat(2, 1fr)',
  },
  [theme.breakpoints.up('md')]: {
    gridTemplateColumns: 'repeat(4, 1fr)',
  },
}));

export const BottomCardsRow = styled(Box)(({ theme }) => ({
  display: 'grid',
  gridTemplateColumns: '1fr',
  gap: theme.spacing(3),
  flex: 1,
  [theme.breakpoints.up('sm')]: {
    gridTemplateColumns: 'repeat(2, 1fr)',
  },
  [theme.breakpoints.up('md')]: {
    gridTemplateColumns: 'repeat(8, 1fr)',
  },
}));

export const ValueCardContainer = styled(Box)(({ theme }) => ({
  [theme.breakpoints.up('md')]: {
    gridColumn: 'span 4',
  },
}));

export const SmallCardContainer = styled(Box)(({ theme }) => ({
  [theme.breakpoints.up('md')]: {
    gridColumn: 'span 2',
  },
}));

// Right section styling
export const RightSection = styled(Box)(({ theme }) => ({
  display: 'grid',
  gridTemplateRows: 'repeat(3, 1fr)',
  gap: theme.spacing(3),
}));
