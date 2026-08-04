import { FC, useCallback, useEffect, useState } from 'react';

import {
  Modal,
  ModalProps,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
} from '@mui/material';

import ButtonAdmin from '@components/UI/admin/ButtonAdmin';
import { imagePlaceholderUrl } from '@constants/urls';
import {
  CreateShipmentStatus,
  SendInvoiceStatus,
  StatusesToHideControls,
} from '@pages/Admin/Orders/components/SelectedOrderModal/constants';
import SortCell from '@pages/Admin/Orders/components/SelectedOrderModal/SortCell';
import {
  CloseModalButton,
  CloseModalIcon,
  ControlsContainer,
  ControlsRow,
  DividerLine,
  ImageCell,
  LoadingProgress,
  ModalContainer,
  ModalContent,
  OrderStatusCell,
  OrderTable,
  ProductsTableWrapper,
  SectionTitle,
  TableBottomWrapper,
  TotalText,
} from '@pages/Admin/Orders/components/SelectedOrderModal/styles';
import {
  getOrder,
  getOrderItems,
  payOrder,
  shipOrder,
} from '@services/http/admin/orders';
import showToast from '@utils/showToast';

import {
  IOrderAdmin,
  IOrderItemAdmin,
  IOrderItemsFilters,
} from '../../../../../types/orders/interfaces';
import {
  OrderProductOrdering,
  OrderProductOrderingPositive,
} from '../../../../../types/orders/types';

interface SelectedOrderModalProps extends Omit<ModalProps, 'children'> {
  selectedOrderId: string | null;
}

const SelectedOrderModal: FC<SelectedOrderModalProps> = ({
  open,
  onClose,
  selectedOrderId,
  ...rest
}) => {
  const [order, setOrder] = useState<IOrderAdmin | null>();
  const [orderItems, setOrderItems] = useState<IOrderItemAdmin[]>([]);
  const [orderItemsFilter, setOrderItemsFilter] = useState<
    Omit<IOrderItemsFilters, 'limit' | 'offset'>
  >({});
  const [hasMore, setHasMore] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isConfirmingPayment, setIsConfirmingPayment] = useState(false);
  const [isCreatingShipment, setIsCreatingShipment] = useState(false);

  const limit = 8;

  const fetchOrder = useCallback(async () => {
    if (selectedOrderId === null) return;

    try {
      const data = await getOrder(selectedOrderId);
      setOrder(data);
    } catch {
      showToast({
        message: 'Error fetching order',
        type: 'error',
      });
      onClose?.({}, 'escapeKeyDown');
    }
  }, [onClose, selectedOrderId]);

  const fetchOrderItems = async (
    filterParams: IOrderItemsFilters,
    inplace?: boolean
  ) => {
    if (selectedOrderId === null) return;

    try {
      setIsLoading(true);
      const data = await getOrderItems(selectedOrderId, {
        ...orderItemsFilter,
        ...filterParams,
      });
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

  const applyOrdering = (ordering: OrderProductOrderingPositive) => {
    const newOrdering: OrderProductOrdering =
      orderItemsFilter.ordering === ordering ? `-${ordering}` : ordering;
    setOrderItemsFilter(prev => {
      const newFilters = { ...prev, ordering: newOrdering };
      void fetchOrderItems({ ...newFilters, offset: 0, limit }, true);
      return newFilters;
    });
  };

  // Manual counterpart to Stripe's webhook-driven confirmation -- for
  // cash_on_delivery (and any card order stuck pending), an admin marks it
  // paid once payment is actually in hand. See admin/orders.ts's payOrder.
  const handleConfirmPayment = async () => {
    if (selectedOrderId === null) return;
    setIsConfirmingPayment(true);
    try {
      const updated = await payOrder(selectedOrderId);
      setOrder(updated);
      showToast({ message: 'Payment confirmed', type: 'success' });
    } catch {
      showToast({ message: 'Error confirming payment', type: 'error' });
    } finally {
      setIsConfirmingPayment(false);
    }
  };

  const handleRejectOrder = () => console.log('Order rejected');
  const handleSendInvoice = () => console.log('Order rejected');

  const handleCreateShipment = async () => {
    if (selectedOrderId === null) return;
    setIsCreatingShipment(true);
    try {
      const updated = await shipOrder(selectedOrderId);
      setOrder(updated);
      showToast({ message: 'Shipment created', type: 'success' });
    } catch {
      showToast({ message: 'Error creating shipment', type: 'error' });
    } finally {
      setIsCreatingShipment(false);
    }
  };

  const renderControls = () => {
    if (!order || StatusesToHideControls.includes(order.status)) return;

    return (
      <ControlsRow>
        <ButtonAdmin variant="outlined" onClick={handleRejectOrder}>
          Reject the order
        </ButtonAdmin>
        {order.status === CreateShipmentStatus && (
          <ButtonAdmin
            variant="contained"
            disabled={isCreatingShipment}
            onClick={handleCreateShipment}
          >
            Create a shipment
          </ButtonAdmin>
        )}
        {order.status === SendInvoiceStatus && (
          <ButtonAdmin variant="contained" onClick={handleSendInvoice}>
            Send an invoice
          </ButtonAdmin>
        )}
      </ControlsRow>
    );
  };

  useEffect(() => {
    if (selectedOrderId === null) {
      setOrder(null);
      setOrderItems([]);
      return;
    }
    void fetchOrder();
    void fetchOrderItems({ offset: 0, limit });
  }, [fetchOrder, selectedOrderId]);

  return (
    <Modal open={open} onClose={onClose} {...rest}>
      {order ? (
        <ModalContainer>
          <CloseModalButton onClick={() => onClose?.({}, 'escapeKeyDown')}>
            <CloseModalIcon />
          </CloseModalButton>
          <ModalContent>
            <SectionTitle>Client Information</SectionTitle>
            <OrderTable>
              <TableHead>
                <TableRow>
                  <TableCell>ID</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Name and Surname</TableCell>
                  <TableCell>Email Address</TableCell>
                  <TableCell>Phone</TableCell>
                  <TableCell>Delivery Address</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                <TableRow>
                  <TableCell>{order.id}</TableCell>
                  <TableCell>
                    <OrderStatusCell status={order.status} />
                  </TableCell>
                  <TableCell>{`${order.contactInfo.firstName} ${order.contactInfo.lastName}`}</TableCell>
                  <TableCell>{order.contactInfo.email}</TableCell>
                  <TableCell>{order.contactInfo.phone}</TableCell>
                  <TableCell>{order.contactInfo.deliveryAddress}</TableCell>
                </TableRow>
              </TableBody>
            </OrderTable>
            <DividerLine />
            <SectionTitle>Order Details</SectionTitle>
            <ProductsTableWrapper>
              <OrderTable className={isLoading ? 'loading' : ''}>
                <TableHead>
                  <TableRow>
                    <TableCell>ID</TableCell>
                    <TableCell>Image</TableCell>
                    <TableCell>Name</TableCell>
                    <TableCell>Category</TableCell>
                    <SortCell
                      isLoading={isLoading}
                      applyOrdering={() => applyOrdering('price')}
                    >
                      Price
                    </SortCell>
                    <SortCell
                      isLoading={isLoading}
                      applyOrdering={() => applyOrdering('quantity')}
                    >
                      Quantity
                    </SortCell>
                    <TableCell>Available</TableCell>
                    <SortCell
                      isLoading={isLoading}
                      applyOrdering={() => applyOrdering('total_price')}
                    >
                      Sum
                    </SortCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {orderItems.map(item => (
                    <TableRow key={item.id}>
                      <TableCell>{item.product.id}</TableCell>
                      <TableCell>
                        <ImageCell
                          src={item.product.image ?? imagePlaceholderUrl}
                        />
                      </TableCell>
                      <TableCell>{item.product.name}</TableCell>
                      <TableCell>{item.product.category?.name ?? ''}</TableCell>
                      <TableCell>${item.price}</TableCell>
                      <TableCell>{item.quantity}</TableCell>
                      <TableCell>{item.availableQuantity ?? 0}</TableCell>
                      <TableCell>${item.totalPrice}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </OrderTable>
              <TableBottomWrapper>
                {hasMore && (
                  <ButtonAdmin
                    onClick={handleLoadMore}
                    variant={'text'}
                    disabled={isLoading}
                    loading={isLoading}
                  >
                    {isLoading ? '⠀' : 'Load More'}
                  </ButtonAdmin>
                )}
              </TableBottomWrapper>
            </ProductsTableWrapper>
            <DividerLine />
            <ControlsContainer>
              <ControlsRow>
                <TotalText>Totals:</TotalText>
                <TotalText>${order.totalCost}</TotalText>
              </ControlsRow>
              {order.status === 'pending' && (
                <ControlsRow>
                  <ButtonAdmin
                    variant="contained"
                    disabled={isConfirmingPayment}
                    onClick={handleConfirmPayment}
                  >
                    Confirm payment
                  </ButtonAdmin>
                </ControlsRow>
              )}
              {renderControls()}
            </ControlsContainer>
          </ModalContent>
        </ModalContainer>
      ) : (
        <LoadingProgress />
      )}
    </Modal>
  );
};

export default SelectedOrderModal;
