import { FC, ReactNode } from 'react';

import CloseIcon from '@mui/icons-material/Close';

import { Container, IconWrapper } from './styles';

interface TagProps {
  /** Text to be displayed on the tag */
  children: ReactNode;
  /** Action to be called when tag is closed */
  onCloseClick?: () => void;
}

/** Tag component, used mainly for displaying applied sorting or filtering */
const Tag: FC<TagProps> = ({ children, onCloseClick }) => {
  return (
    <Container>
      {children}
      <IconWrapper onClick={onCloseClick} aria-label={`Remove ${children}`}>
        <CloseIcon />
      </IconWrapper>
    </Container>
  );
};

export default Tag;
