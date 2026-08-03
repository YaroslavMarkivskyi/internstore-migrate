import React from 'react';

import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';

import { ArrowButtonWrapper, StyledArrowButton } from './styles';

interface ArrowButtonProps {
  onClick?: () => void;
}

type Direction = 'left' | 'right';

interface UnifiedArrowButtonProps extends ArrowButtonProps {
  direction: Direction;
}

const ArrowButton: React.FC<UnifiedArrowButtonProps> = ({
  onClick,
  direction,
}) => {
  const Icon = direction === 'left' ? ChevronLeftIcon : ChevronRightIcon;

  return (
    <ArrowButtonWrapper side={direction}>
      <StyledArrowButton onClick={onClick}>
        <Icon sx={{ color: '#555' }} fontSize="large" />
      </StyledArrowButton>
    </ArrowButtonWrapper>
  );
};

export default ArrowButton;
