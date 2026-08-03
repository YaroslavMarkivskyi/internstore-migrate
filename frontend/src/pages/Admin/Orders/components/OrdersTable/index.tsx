import { memo } from 'react';

import SwapVertIcon from '@mui/icons-material/SwapVert';
import {
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
} from '@mui/material';

import colors from '@constants/colors';
import { TableSortButton } from '@pages/Admin/Products/components/ProductsContent/components/ProductsTable/styles';

import { IOrderAdmin } from '../../../../../types/orders/interfaces';

import {
  OrderStatusCell,
  StyledTableRow,
  TableBox,
  TableContainer,
  TableHeadCell,
} from './styles';

import { OrderOrderingPositive } from 'src/types/orders/types';

const OrdersTable = ({
  orders,
  isLoading,
  onOrderSelected,
  setOrdering,
}: {
  orders: IOrderAdmin[];
  isLoading: boolean;
  setOrdering: (newOrdering: OrderOrderingPositive) => void;
  onOrderSelected: (orderId: string) => void;
}) => {
  return (
    <TableBox>
      <TableContainer>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>
                <TableHeadCell>
                  ID
                  <TableSortButton
                    size="small"
                    onClick={() => setOrdering('id')}
                  >
                    <SwapVertIcon />
                  </TableSortButton>
                </TableHeadCell>
              </TableCell>
              <TableCell>
                <TableHeadCell>
                  Date and Time
                  <TableSortButton
                    size="small"
                    onClick={() => setOrdering('created_at')}
                  >
                    <SwapVertIcon />
                  </TableSortButton>
                </TableHeadCell>
              </TableCell>
              <TableCell>
                <TableHeadCell>Customer ID</TableHeadCell>
              </TableCell>
              <TableCell>
                <TableHeadCell>Phone</TableHeadCell>
              </TableCell>
              <TableCell>
                <TableHeadCell>Delivery Address</TableHeadCell>
              </TableCell>
              <TableCell>
                <TableHeadCell>Items Amount</TableHeadCell>
              </TableCell>
              <TableCell>
                <TableHeadCell>Status</TableHeadCell>
              </TableCell>
              <TableCell>
                <TableHeadCell>Sum</TableHeadCell>
              </TableCell>
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
              orders.map(order => (
                <StyledTableRow
                  key={order.id}
                  onClick={() => onOrderSelected(order.id)}
                >
                  <TableCell>{order.id}</TableCell>
                  <TableCell>
                    {order.createdAt.toLocaleString('en-Us').replace(',', '')}
                  </TableCell>
                  <TableCell>{order.contactInfo.email}</TableCell>
                  <TableCell>{order.contactInfo.phone}</TableCell>
                  <TableCell>{order.contactInfo.deliveryAddress}</TableCell>
                  <TableCell>{order.itemsAmount}</TableCell>
                  <TableCell>
                    <OrderStatusCell status={order.status} />
                  </TableCell>
                  <TableCell>{order.totalCost}</TableCell>
                </StyledTableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </TableBox>
  );
};

export default memo(OrdersTable);
