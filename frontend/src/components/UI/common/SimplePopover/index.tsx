import React, {
  cloneElement,
  FC,
  isValidElement,
  ReactElement,
  ReactNode,
  useState,
} from 'react';

import { ButtonProps, Popover, PopoverProps } from '@mui/material';

import { TriggerWrapper } from './styles';

export interface PopoverChildProps {
  onRequestClose?: () => void;
}

interface SimplePopoverProps extends Omit<PopoverProps, 'open' | 'anchorEl'> {
  /** Function to be called when menu is closed */
  onClose?: () => void;
  /** Element that will trigger the Menu to open */
  trigger: ReactNode;
  children: ReactElement<PopoverChildProps>;
}

/** SimplePopover component for creating elements like Filtering or Sorting. You do not have to control button state
 * to change color, color will change automatically depending on menu state. See stories for examples. */
const SimplePopover: FC<SimplePopoverProps> = ({
  onClose,
  trigger,
  children,
  ...rest
}) => {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);

  const handleTriggerClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    onClose?.();
  };

  return (
    <>
      <TriggerWrapper onClick={handleTriggerClick}>
        {isValidElement<ButtonProps>(trigger) &&
          cloneElement(trigger, {
            variant: open ? 'contained' : 'outlined',
            ...trigger.props,
          })}
      </TriggerWrapper>
      <Popover
        {...rest}
        open={open}
        anchorEl={anchorEl}
        onClose={handleMenuClose}
      >
        {cloneElement(children, {
          ...children.props,
          onRequestClose: handleMenuClose,
        })}
      </Popover>
    </>
  );
};

export default SimplePopover;
