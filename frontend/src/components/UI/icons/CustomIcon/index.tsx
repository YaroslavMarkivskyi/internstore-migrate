import { FC } from 'react';

import { Box, SxProps } from '@mui/material';

interface CustomIconProps {
  className?: string;
  src: string;
  alt?: string;
  sx?: SxProps;
}

export interface CustomIconPartialProps {
  className?: string;
  sx?: SxProps;
}

const CustomIcon: FC<CustomIconProps> = ({ className, alt, src, sx }) => {
  return (
    <Box component={'img'} src={src} alt={alt} className={className} sx={sx} />
  );
};

export default CustomIcon;
