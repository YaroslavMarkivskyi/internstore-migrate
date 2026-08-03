import { FC, useEffect, useState } from 'react';

import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import {
  AccordionDetails,
  Box,
  CircularProgress,
  Collapse,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';

import OrderStatus from '@components/UI/common/OrderStatus';
import ButtonCustomer from '@components/UI/customer/ButtonCustomer';
import { imagePlaceholderUrl } from '@constants/urls';
import { statusDescriptionMap } from '@pages/Customer/Orders/components/Order/constants';
import {
  ContactDetailsRow,
  ContactDetailsText,
  ContactDetailsTextTitle,
  ContactDetailsWrapper,
  ControlsButton,
  ControlsWrapper,
  DividerHorizontal,
  ImageCell,
  ImageCellWrapper,
  OrderContent,
  OrderHeader,
  OrderHeaderContent,
  OrderStatusDescriptionText,
  OrderStatusWrapper,
  OrderTable,
  OrderTitle,
  OrderWrapper,
  PayWithStripeButton,
  PayWithStripeIcon,
  ProductsWrapper,
  ProductWrapper,
  TableBottomWrapper,
  TotalsRow,
  TotalsText,
} from '@pages/Customer/Orders/components/Order/styles';
import { getOrderItems } from '@services/http/public/orders';
import showToast from '@utils/showToast';

import {
  IOrderItemPublic,
  IOrderPublic,
} from '../../../../../types/orders/interfaces';
import { PaginationQueryParams } from '../../../../../types/pagination/interfaces';

const formatDate = (date: Date) => {
  const formatted = date.toLocaleString('en-GB', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  });

  return formatted.replace(',', ' at');
};

interface OrderProps {
  order: IOrderPublic;
}

const Order: FC<OrderProps> = ({ order }) => {
  // Need to control Accordion to be able to fetch order details only when Accordion is opened
  const [expanded, setExpanded] = useState<boolean>(false);
  const [pendingExpand, setPendingExpand] = useState<boolean>(false);

  const [orderItems, setOrderItems] = useState<IOrderItemPublic[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const limit = 4;

  const fetchOrderItems = async (
    filterParams: PaginationQueryParams,
    inplace?: boolean
  ) => {
    try {
      setIsLoading(true);
      const data = await getOrderItems(order.id, filterParams);
      let newItems;
      if (inplace) {
        newItems = data.results;
      } else {
        newItems = data.results.filter(
          item => !orderItems.some(existing => existing.id === item.id)
        );
      }
      setOrderItems(prev => (inplace ? newItems : [...prev, ...newItems]));
      setHasMore(!!data.next);
    } catch {
      showToast({
        message: 'Error fetching order products',
        type: 'error',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleLoadMore = () => {
    void fetchOrderItems({ offset: orderItems.length, limit });
  };

  const handleAccordionToggle = async () => {
    if (!expanded && orderItems.length === 0) {
      setPendingExpand(true);
      await fetchOrderItems({ offset: 0, limit }, true);
      setPendingExpand(false);
      setExpanded(true);
    } else {
      setExpanded(!expanded);
    }
  };

  useEffect(() => {
    setOrderItems([]);
  }, [order.id]);

  return (
    <OrderWrapper
      className={pendingExpand ? 'loading' : ''}
      elevation={0}
      disableGutters
      expanded={expanded}
      onChange={handleAccordionToggle}
    >
      <OrderHeader expandIcon={<ExpandMoreIcon />}>
        <OrderHeaderContent>
          <Collapse
            in={pendingExpand}
            orientation="horizontal"
            timeout={300}
            unmountOnExit
            sx={{ mr: 1 }}
          >
            <CircularProgress size="1rem" />
          </Collapse>
          <OrderTitle>
            Order #{order.id}, {formatDate(order.createdAt)}
          </OrderTitle>
          <OrderStatusWrapper>
            <OrderStatus status={order.status} />
            <OrderStatusDescriptionText>
              {statusDescriptionMap[order.status]}
            </OrderStatusDescriptionText>
          </OrderStatusWrapper>
        </OrderHeaderContent>
      </OrderHeader>
      <AccordionDetails>
        <DividerHorizontal />
        <OrderContent>
          <ContactDetailsWrapper>
            <Typography fontWeight={600}>Contact Details</Typography>
            <ContactDetailsRow>
              <ContactDetailsTextTitle>Name:</ContactDetailsTextTitle>
              <ContactDetailsText>
                {order.contactInfo.firstName} {order.contactInfo.lastName}
              </ContactDetailsText>
            </ContactDetailsRow>
            <ContactDetailsRow>
              <ContactDetailsTextTitle>Phone Number:</ContactDetailsTextTitle>
              <ContactDetailsText>{order.contactInfo.phone}</ContactDetailsText>
            </ContactDetailsRow>
            <ContactDetailsRow>
              <ContactDetailsTextTitle>Email:</ContactDetailsTextTitle>
              <ContactDetailsText>{order.contactInfo.email}</ContactDetailsText>
            </ContactDetailsRow>
            <ContactDetailsRow>
              <ContactDetailsTextTitle>
                Delivery Address:
              </ContactDetailsTextTitle>
              <ContactDetailsText>
                {order.contactInfo.deliveryAddress}
              </ContactDetailsText>
            </ContactDetailsRow>
          </ContactDetailsWrapper>
          <ProductsWrapper>
            <Box>
              <OrderTable className={isLoading ? 'loading' : ''}>
                <TableHead>
                  <TableRow>
                    <TableCell>Product</TableCell>
                    <TableCell>Price</TableCell>
                    <TableCell>Quantity</TableCell>
                    <TableCell>Sum</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {orderItems.map(item => (
                    <TableRow key={item.id}>
                      <TableCell>
                        <ProductWrapper>
                          <ImageCellWrapper>
                            <ImageCell
                              src={item.product.image ?? imagePlaceholderUrl}
                            />
                          </ImageCellWrapper>
                          {item.product.name}
                        </ProductWrapper>
                      </TableCell>
                      <TableCell>${item.price}</TableCell>
                      <TableCell>{item.quantity}</TableCell>
                      <TableCell>${item.totalPrice}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </OrderTable>
              <TableBottomWrapper>
                {hasMore && (
                  <ButtonCustomer
                    onClick={handleLoadMore}
                    variant={'text'}
                    disabled={isLoading}
                    loading={isLoading}
                  >
                    {isLoading ? '⠀' : 'Load More'}
                  </ButtonCustomer>
                )}
              </TableBottomWrapper>
            </Box>
            <DividerHorizontal />
            <TotalsRow>
              <TotalsText>Totals</TotalsText>
              <TotalsText>${order.totalCost}</TotalsText>
            </TotalsRow>
            {order.status === 'new' && (
              <ControlsWrapper>
                <ControlsButton variant={'contained'}>
                  Cancel the order
                </ControlsButton>
              </ControlsWrapper>
            )}
            {order.status === 'pending' && (
              <ControlsWrapper>
                <PayWithStripeButton>
                  Pay with <PayWithStripeIcon />
                </PayWithStripeButton>
              </ControlsWrapper>
            )}
          </ProductsWrapper>
        </OrderContent>
      </AccordionDetails>
    </OrderWrapper>
  );
};

export default Order;
