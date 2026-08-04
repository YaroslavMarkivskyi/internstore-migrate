import { FC, useEffect, useRef, useState } from 'react';

import ArrowForwardOutlinedIcon from '@mui/icons-material/ArrowForwardOutlined';
import ContentCopyOutlinedIcon from '@mui/icons-material/ContentCopyOutlined';
import CreateOutlinedIcon from '@mui/icons-material/CreateOutlined';
import DeleteOutlineOutlinedIcon from '@mui/icons-material/DeleteOutlineOutlined';
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import PreviewOutlinedIcon from '@mui/icons-material/PreviewOutlined';
import {
  Box,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Typography,
} from '@mui/material';

import { isAxiosError } from 'axios';

import ButtonAdmin from '@components/UI/admin/ButtonAdmin';
import { IconWrapper } from '@components/UI/common/Icons/styles';
import MenuPopup, { MenuItem } from '@components/UI/common/MenuPopup';
import SimplePopover from '@components/UI/common/SimplePopover';
import MoveToStockMenu from '@pages/Admin/Stocks/components/MoveToStock';
import { stockService } from '@services/http';
import showToast from '@utils/showToast';

import { IStockProduct } from 'src/types/stocks/interfaces';

export interface StockProductMenuPopupProps {
  product: IStockProduct;
  onEditQuantity?: () => void;
  onMoveToStockSuccess?: () => void;
  onDeleteSuccess?: () => void;
  showDuplicateOption?: boolean;
}

// Wrapper component for MoveToStockMenu to handle the onRequestClose prop from SimplePopover
const MoveToStockWrapper: FC<{
  productStockEntry: IStockProduct;
  sourceStockId: string;
  onRequestClose?: () => void;
  onSuccess?: () => void;
}> = ({ productStockEntry, sourceStockId, onRequestClose, onSuccess }) => {
  const handleClose = () => {
    if (onRequestClose) {
      onRequestClose();
    }
  };

  return (
    <MoveToStockMenu
      sourceStockId={sourceStockId}
      productStockEntry={productStockEntry}
      onClose={handleClose}
      onSuccess={onSuccess}
    />
  );
};

const StockProductMenuPopup: FC<StockProductMenuPopupProps> = ({
  product,
  onEditQuantity,
  onMoveToStockSuccess,
  onDeleteSuccess,
  showDuplicateOption = true,
}) => {
  const [showMoveToStock, setShowMoveToStock] = useState<boolean>(false);
  const moveToStockButtonRef = useRef<HTMLButtonElement>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleEditQuantity = () => {
    if (onEditQuantity) {
      onEditQuantity();
    }
  };

  const handleDuplicateProduct = () => {
    console.log(`Duplicate product with ID: ${product.product.id}`);
  };

  const handleMoveToStock = () => {
    setShowMoveToStock(true);
  };

  const handleCloseMoveToStock = () => {
    setShowMoveToStock(false);
  };

  const handlePreviewProduct = () => {
    console.log(`Preview product with ID: ${product.product.id}`);
  };

  const handleDeleteProduct = () => {
    setDeleteDialogOpen(true);
  };

  const handleCloseDeleteDialog = () => {
    if (isDeleting) return;
    setDeleteDialogOpen(false);
  };

  const confirmDeleteProduct = async () => {
    setIsDeleting(true);
    try {
      await stockService.deleteStockItem(product.stockId, product.id);
      showToast({ message: 'Product removed from stock', type: 'success' });
      setDeleteDialogOpen(false);
      onDeleteSuccess?.();
    } catch (error) {
      // Surfaces delete_stock_item's real 409 reason (item held by an
      // in-progress reservation) instead of a generic message, same
      // pattern as StockModalForm's own delete-stock error handling.
      const detail = isAxiosError(error)
        ? (error.response?.data as { detail?: string } | undefined)?.detail
        : undefined;
      showToast({
        message: detail ?? 'Error removing product from stock',
        type: 'error',
      });
    } finally {
      setIsDeleting(false);
    }
  };

  // Programmatically click the hidden button to open the popover when showMoveToStock changes
  useEffect(() => {
    if (showMoveToStock && moveToStockButtonRef.current) {
      moveToStockButtonRef.current.click();
      setShowMoveToStock(false); // Reset state after click
    }
  }, [showMoveToStock]);

  const menuOptions: MenuItem[] = [
    {
      label: 'Edit quantity',
      onClick: handleEditQuantity,
      startComponent: (
        <IconWrapper>
          <CreateOutlinedIcon />
        </IconWrapper>
      ),
    },
    ...(showDuplicateOption
      ? [
          {
            label: 'Duplicate the product',
            onClick: handleDuplicateProduct,
            disabled: product.quantity <= 0,
            startComponent: (
              <IconWrapper>
                <ContentCopyOutlinedIcon />
              </IconWrapper>
            ),
          },
        ]
      : []),
    {
      label: 'Move to stock',
      onClick: handleMoveToStock,
      startComponent: (
        <IconWrapper>
          <ArrowForwardOutlinedIcon />
        </IconWrapper>
      ),
    },
    {
      label: 'Preview',
      onClick: handlePreviewProduct,
      startComponent: (
        <IconWrapper>
          <PreviewOutlinedIcon />
        </IconWrapper>
      ),
    },
    {
      label: 'Delete',
      onClick: handleDeleteProduct,
      startComponent: (
        <IconWrapper>
          <DeleteOutlineOutlinedIcon />
        </IconWrapper>
      ),
    },
  ];

  // Handle click event propagation
  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
  };

  return (
    <Box onClick={handleClick} sx={{ position: 'relative' }}>
      {/* Original menu popup */}
      <MenuPopup
        options={menuOptions}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
      >
        <IconButton aria-label="product-actions">
          <MoreHorizIcon fontSize="small" />
        </IconButton>
      </MenuPopup>

      {/* Hidden SimplePopover for MoveToStockMenu */}
      <SimplePopover
        trigger={
          <IconButton
            ref={moveToStockButtonRef}
            sx={{
              position: 'absolute',
              visibility: 'hidden',
              width: 0,
              height: 0,
              padding: 0,
            }}
          >
            <ArrowForwardOutlinedIcon />
          </IconButton>
        }
        onClose={handleCloseMoveToStock}
        anchorOrigin={{
          vertical: 'center',
          horizontal: 'center',
        }}
        transformOrigin={{
          vertical: 'center',
          horizontal: 'center',
        }}
        slotProps={{
          paper: {
            sx: {
              maxWidth: '90vw',
              maxHeight: '90vh',
              overflowY: 'auto',
            },
          },
        }}
      >
        <MoveToStockWrapper
          productStockEntry={product}
          sourceStockId={product.stockId}
          onSuccess={onMoveToStockSuccess}
        />
      </SimplePopover>

      <Dialog open={deleteDialogOpen} onClose={handleCloseDeleteDialog}>
        <DialogTitle>Remove product from this stock?</DialogTitle>
        <DialogContent>
          <Typography variant="body1">
            This removes all {product.quantity} unit(s) of this product from
            the stock. This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ justifyContent: 'center', gap: 2, pb: 3 }}>
          <ButtonAdmin
            variant="outlined"
            fullWidth
            disabled={isDeleting}
            onClick={handleCloseDeleteDialog}
          >
            Cancel
          </ButtonAdmin>
          <ButtonAdmin
            variant="contained"
            fullWidth
            disabled={isDeleting}
            onClick={confirmDeleteProduct}
          >
            Remove
          </ButtonAdmin>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
export default StockProductMenuPopup;
