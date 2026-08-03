import { FC } from 'react';

import DashboardTiles from './DashboardTiles';
import { DashboardTitle, StyledContainer } from './styles';
import UnprocessedOrders from './UnprocessedOrders';

const DashboardContent: FC = () => {
  return (
    <StyledContainer>
      <DashboardTitle variant="h4" component="h1">
        Dashboard
      </DashboardTitle>
      <DashboardTiles />
      <UnprocessedOrders />
    </StyledContainer>
  );
};

export default DashboardContent;
