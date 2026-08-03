import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { Box } from '@mui/material';
import { styled } from '@mui/material/styles';

import colors from '../../../../constants/colors';

export const ImageContainer = styled(Box)({
  width: 70,
  height: 78,
});

export const EmptyImage = styled(Box)({
  width: '100%',
  height: '100%',
  border: `1px dashed ${colors.backgroundDisabled}`,
  borderRadius: 3,
});

export const ImageWrapper = styled(Box)({
  width: '100%',
  height: '100%',
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  border: `1px solid ${colors.border}`,
  borderRadius: 5,
  position: 'relative',
});

export const DeleteContainer = styled(Box)({
  position: 'absolute',
  top: 0,
  left: 0,
  width: '100%',
  height: '100%',
  backgroundColor: colors.backgroundDisabled,
  cursor: 'pointer',
  opacity: 0,
  transition: 'all 0.1s ease-in',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  '&:hover': {
    opacity: 1,
    backgroundColor: `${colors.backgroundDisabled}E6`, // 0.9 opacity bg
  },
});

export const DeleteIcon = styled(DeleteOutlineIcon)({
  fill: colors.secondary.accent100,
});

export const Image = styled('img')({
  width: '100%',
  height: '100%',
  objectFit: 'contain',
});
