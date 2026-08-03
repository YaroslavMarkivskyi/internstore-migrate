import { memo, useEffect, useRef, useState } from 'react';

import RefreshIcon from '@mui/icons-material/Refresh';
import {
  CircularProgress,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
} from '@mui/material';

import OrderStatus from '@components/UI/common/OrderStatus';
import colors from '@constants/colors';
import { getOrders } from '@services/http/admin/orders';

import useFetcher from '../../../../../../hooks/useFetcher';

import {
  RefreshContainer,
  RefreshCountdown,
  StatusCell,
  StyledPaper,
  StyledTableContainer,
  TableDivider,
  TitleContainer,
  TitleText,
} from './styles';

import { IOrderAdmin } from 'src/types/orders/interfaces';

const REFRESH_INTERVAL = 60;

const UnprocessedOrders = () => {
  const {
    items: orders,
    isLoading,
    refresh,
  } = useFetcher({
    fetcher: getOrders,
    params: {
      limit: 5,
      offset: 0,
      status: 'new',
    },
  });

  const [timeLeft, setTimeLeft] = useState(REFRESH_INTERVAL);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const countdownRef = useRef<NodeJS.Timeout | null>(null);

  const resetCountdown = () => {
    setTimeLeft(REFRESH_INTERVAL);
    if (countdownRef.current) clearInterval(countdownRef.current);
    countdownRef.current = setInterval(() => {
      setTimeLeft(prev => (prev > 0 ? prev - 1 : 0));
    }, 1000);
  };

  const handleManualRefresh = async () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    await refresh();
    startInterval();
  };

  const startInterval = () => {
    resetCountdown();

    intervalRef.current = setInterval(async () => {
      await refresh();
      resetCountdown();
    }, REFRESH_INTERVAL * 1000);
  };

  useEffect(() => {
    startInterval();

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, []);

  return (
    <StyledPaper aria-label="Unprocessed Orders Section">
      <TitleContainer>
        <TitleText variant="h6" component="h2">
          Unprocessed Orders
        </TitleText>

        <RefreshContainer>
          <RefreshCountdown>Next refresh in: {timeLeft}s</RefreshCountdown>
          <IconButton
            aria-label="Refresh orders"
            onClick={handleManualRefresh}
            disabled={isLoading}
          >
            <RefreshIcon fontSize="large" sx={{ color: colors.dashboard }} />
          </IconButton>
        </RefreshContainer>
      </TitleContainer>
      <TableDivider />

      <StyledTableContainer>
        <Table aria-label="Unprocessed orders table">
          <TableHead>
            <TableRow>
              <TableCell>Order ID</TableCell>
              <TableCell>Customer Name</TableCell>
              <TableCell>Date</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Price</TableCell>
              <TableCell>Phone Number</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  <CircularProgress
                    sx={{ color: colors.secondary.accent500 }}
                  />
                </TableCell>
              </TableRow>
            ) : (
              orders.map((order: IOrderAdmin) => (
                <TableRow
                  key={order.id}
                  hover
                  tabIndex={-1}
                  aria-label={`Order ${order.id} from ${order.customer}`}
                >
                  <TableCell>{order.id}</TableCell>
                  <TableCell>
                    {order.contactInfo.firstName} {order.contactInfo.lastName}
                  </TableCell>
                  <TableCell>{order.createdAt.toLocaleString()}</TableCell>
                  <StatusCell>
                    <OrderStatus status={order.status} />
                  </StatusCell>
                  <TableCell>{order.totalCost}</TableCell>
                  <TableCell>{order.contactInfo.phone}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </StyledTableContainer>
    </StyledPaper>
  );
};

export default memo(UnprocessedOrders);
