import CameraAltIcon from '@mui/icons-material/CameraAlt';
import { Box } from '@mui/material';
import { styled } from '@mui/material/styles';

import colors from '../../../../constants/colors';

export const ImageContainer = styled(Box)({
  border: `1px solid ${colors.border}`,
  borderRadius: 10,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: colors.secondary.background,
  height: 185,
});

export const PlaceholderIcon = styled(CameraAltIcon)({
  color: colors.backgroundDisabled,
  width: 107,
  height: 95,
});

export const Image = styled('img')({
  width: '100%',
  height: '100%',
  objectFit: 'contain',
});
