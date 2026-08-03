import { FC } from 'react';

import { Typography } from '@mui/material';

import logoImage from '../../../../assets/logo.svg';

import {
  BrandName,
  LogoContainer,
  LogoImage,
  LogoTextContainer,
} from './styles';

interface LogoProps {
  /** Whether to display Admin Panel text or not */
  isAdmin?: boolean;
  /** Action to be called on Click */
  onClick?: () => void;
}

const Logo: FC<LogoProps> = ({ isAdmin = false, onClick }) => {
  return (
    <LogoContainer onClick={onClick}>
      <LogoImage src={logoImage} alt="InternStore Logo" />
      <LogoTextContainer>
        <BrandName variant="subtitle1">InternStore</BrandName>
        {isAdmin && (
          <Typography variant="caption" color="text.primary">
            Admin Panel
          </Typography>
        )}
      </LogoTextContainer>
    </LogoContainer>
  );
};

export default Logo;
