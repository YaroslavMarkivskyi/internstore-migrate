import { FC, ReactNode } from 'react';

import { SxProps, Typography } from '@mui/material';

import {
  ContentWrapper,
  MenuContent,
  MenuWrapper,
} from '@components/SideMenu/styles';

interface SideMenuProps {
  title: string;
  menuContent: ReactNode;
  menuContentSx?: SxProps;
  content: ReactNode;
  contentSx?: SxProps;
}

const SideMenu: FC<SideMenuProps> = ({
  title,
  menuContent,
  content,
  menuContentSx,
  contentSx,
}) => {
  return (
    <>
      <MenuWrapper>
        <Typography fontWeight={500}>{title}</Typography>
        <MenuContent sx={menuContentSx}>{menuContent}</MenuContent>
      </MenuWrapper>
      <ContentWrapper sx={contentSx}>{content}</ContentWrapper>
    </>
  );
};

export default SideMenu;
