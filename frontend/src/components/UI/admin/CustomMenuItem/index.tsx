import React, { FC, ReactNode } from 'react';

import { ListItemText, MenuItemProps, SxProps } from '@mui/material';

import { OptionItem, StartComponentWrapper } from './styles';

interface InsertableComponent {
  disabled?: boolean;
  checked?: boolean;
  sx?: SxProps;
}

export interface CustomMenuOption {
  /** Component to render in the start position of the MenuItem. Optional */
  startComponent?: ReactNode;
  /** Component to render in the end position of the MenuItem. Optional */
  endComponent?: ReactNode;
}

type CustomMenuItemProps = MenuItemProps & CustomMenuOption;

/** Custom MenuItem component used for various other components like MenuPopup or SimplePopover */
const CustomMenuItem: FC<CustomMenuItemProps> = ({
  children,
  startComponent,
  endComponent,
  ...props
}) => {
  const iconProps: InsertableComponent = {
    disabled: true,
    checked: props.selected,
  };
  return (
    <OptionItem {...props}>
      {startComponent &&
        React.isValidElement<InsertableComponent>(startComponent) && (
          <StartComponentWrapper>
            {React.cloneElement(startComponent, {
              ...iconProps,
              ...startComponent.props,
            })}
          </StartComponentWrapper>
        )}
      <ListItemText> {children}</ListItemText>
      {endComponent &&
        React.isValidElement<InsertableComponent>(endComponent) &&
        React.cloneElement(endComponent, {
          ...iconProps,
          ...endComponent.props,
        })}
    </OptionItem>
  );
};

export default CustomMenuItem;
