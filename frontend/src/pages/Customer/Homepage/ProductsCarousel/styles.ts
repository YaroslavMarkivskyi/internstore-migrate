import { Box, IconButton, styled } from '@mui/material';

export const CarouselResponsiveness = {
  superLargeDesktop: {
    breakpoint: { max: 4000, min: 1536 },
    items: 6,
    slidesToSlide: 2,
  },
  desktop: {
    breakpoint: { max: 1536, min: 1200 },
    items: 4,
    slidesToSlide: 2,
  },
  smallDesktop: {
    breakpoint: { max: 1200, min: 900 },
    items: 3,
    slidesToSlide: 2,
  },
  tablet: {
    breakpoint: { max: 900, min: 600 },
    items: 2,
    slidesToSlide: 2,
  },
  mobile: {
    breakpoint: { max: 600, min: 0 },
    items: 1,
  },
};

export const ArrowButtonWrapper = styled(Box)<{ side: 'left' | 'right' }>(
  ({ side }) => ({
    position: 'absolute',
    [side]: 10,
    top: '50%',
    transform: 'translateY(-50%)',
    zIndex: 2,
  })
);

export const StyledArrowButton = styled(IconButton)({
  backgroundColor: 'white',
  boxShadow: '0px 2px 10px rgba(0, 0, 0, 0.2)',
  width: 40,
  height: 40,
  '&:hover': {
    backgroundColor: '#f5f5f5',
  },
});
