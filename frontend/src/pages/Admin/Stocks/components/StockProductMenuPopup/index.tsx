import { FC, useEffect, useRef, useState } from 'react';

import ArrowForwardOutlinedIcon from '@mui/icons-material/ArrowForwardOutlined';
import ContentCopyOutlinedIcon from '@mui/icons-material/ContentCopyOutlined';
import CreateOutlinedIcon from '@mui/icons-material/CreateOutlined';
import DeleteOutlineOutlinedIcon from '@mui/icons-material/DeleteOutlineOutlined';
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import PreviewOutlinedIcon from '@mui/icons-material/PreviewOutlined';
import { Box, IconButton } from '@mui/material';

import { IconWrapper } from '@components/UI/common/Icons/styles';
import MenuPopup, { MenuItem } from '@components/UI/common/MenuPopup';
import SimplePopover from '@components/UI/common/SimplePopover';
import MoveToStockMenu from '@pages/Admin/Stocks/components/MoveToStock';

import { IStockProduct } from 'src/types/stocks/interfaces';

export interface StockProductMenuPopupProps {
  product: IStockProduct;
  onEditQuantity?: () => void;
  onMoveToStockSuccess?: () => void;
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
  showDuplicateOption = true,
}) => {
  const [showMoveToStock, setShowMoveToStock] = useState<boolean>(false);
  const moveToStockButtonRef = useRef<HTMLButtonElement>(null);

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
    console.log(`Delete product with ID: ${product.product.id}`);
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
    </Box>
  );
};
export default StockProductMenuPopup;
