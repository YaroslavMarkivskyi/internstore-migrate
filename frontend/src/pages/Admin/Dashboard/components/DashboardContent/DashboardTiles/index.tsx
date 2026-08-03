import { memo } from 'react';

import StatCard from './components/StatCard';
import TemperatureCard from './components/TempCard';
import { statsData, StatsDataType } from './mockData';
import {
  BottomCardsRow,
  GridContainer,
  LeftSection,
  RightSection,
  SmallCardContainer,
  TilesContainer,
  TopCardsRow,
  ValueCardContainer,
} from './styles';

const DashboardTiles = () => {
  const data: StatsDataType = statsData;

  return (
    <TilesContainer aria-label="Dashboard Statistics">
      <GridContainer>
        <LeftSection aria-label="Main Statistics">
          <TopCardsRow>
            <StatCard title="Sales this week" value={data.salesThisWeek} />
            <StatCard title="New orders" value={data.newOrders} />
            <StatCard title="Pending payment" value={data.pendingPayment} />
            <StatCard title="Paid orders" value={data.paidOrders} />
          </TopCardsRow>

          <BottomCardsRow>
            <ValueCardContainer>
              <StatCard title="Value this week" value={data.valueThisWeek} />
            </ValueCardContainer>

            <SmallCardContainer>
              <StatCard title="Cancelled orders" value={data.cancelledOrders} />
            </SmallCardContainer>

            <SmallCardContainer>
              <StatCard title="Rejected orders" value={data.rejectedOrders} />
            </SmallCardContainer>
          </BottomCardsRow>
        </LeftSection>

        <RightSection aria-label="Temperature Statistics">
          {data.temperatures.map((temp, index) => (
            <TemperatureCard key={index} store={temp.store} temp={temp.temp} />
          ))}
        </RightSection>
      </GridContainer>
    </TilesContainer>
  );
};

export default memo(DashboardTiles);
