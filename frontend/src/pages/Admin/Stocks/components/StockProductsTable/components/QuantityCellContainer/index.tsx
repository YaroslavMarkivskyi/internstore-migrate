import { useState } from 'react';

import { useParams } from 'react-router';

import { updateStockProduct } from '@services/http/admin/stocks';
import showToast from '@utils/showToast';

import EditableQuantityCell from '../EditableQuantityCell';

interface QuantityCellContainerProps {
  productEntryId: string;
  quantity: number;
  isEditing: boolean;
  onEditComplete: () => void;
  onUpdateSuccess?: () => void;
}

const QuantityCellContainer = ({
  productEntryId,
  quantity,
  isEditing,
  onEditComplete,
  onUpdateSuccess,
}: QuantityCellContainerProps) => {
  const [isUpdating, setIsUpdating] = useState(false);
  const { stockId } = useParams<{ stockId: string }>();

  const handleSave = async (newValue: number) => {
    if (newValue === quantity) {
      // No change, just exit edit mode
      onEditComplete();
      return;
    }

    try {
      setIsUpdating(true);
      await updateStockProduct(stockId as string, productEntryId, {
        quantity: newValue,
      });

      showToast({
        message: 'Quantity updated successfully',
        type: 'success',
      });

      // Call the success handler if provided
      if (onUpdateSuccess) {
        onUpdateSuccess();
      }

      onEditComplete();
    } catch (error) {
      console.error('Failed to update quantity:', error);
      showToast({
        message: 'Failed to update quantity',
        type: 'error',
      });
    } finally {
      setIsUpdating(false);
    }
  };

  const handleCancel = () => {
    onEditComplete();
  };

  return (
    <EditableQuantityCell
      value={quantity}
      isEditing={isEditing && !isUpdating}
      onSave={handleSave}
      onCancel={handleCancel}
    />
  );
};

export default QuantityCellContainer;
