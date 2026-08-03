import React, { MouseEventHandler, ReactNode } from 'react';

interface CustomMenuItemMockProps {
  children: string;
  onClick?: MouseEventHandler<HTMLDivElement>;
  startComponent?: ReactNode;
}

const CustomMenuItemMock: React.FC<CustomMenuItemMockProps> = ({
  children,
  onClick,
  startComponent,
}) => {
  return (
    <div
      onClick={onClick}
      data-testid={`menu-item-${children.trim().toLowerCase().replace(/\s+/g, '-')}`}
    >
      {startComponent && <div>{startComponent}</div>}
      {children}
    </div>
  );
};

export default CustomMenuItemMock;
