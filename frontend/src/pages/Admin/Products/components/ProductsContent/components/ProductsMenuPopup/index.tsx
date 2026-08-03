import { Dispatch, FC, SetStateAction, useRef, useState } from 'react';

import { useNavigate } from 'react-router';

import ArrowForwardOutlinedIcon from '@mui/icons-material/ArrowForwardOutlined';
import ContentCopyOutlinedIcon from '@mui/icons-material/ContentCopyOutlined';
import CreateOutlinedIcon from '@mui/icons-material/CreateOutlined';
import DeleteOutlineOutlinedIcon from '@mui/icons-material/DeleteOutlineOutlined';
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import PreviewOutlinedIcon from '@mui/icons-material/PreviewOutlined';
import { IconButton } from '@mui/material';

import {
  IconButtonStyle,
  IconWrapper,
} from '@components/UI/common/Icons/styles';
import MenuPopup, { MenuItem } from '@components/UI/common/MenuPopup';
import { deleteProduct } from '@services/http/admin/products';
import showToast from '@utils/showToast';

import DeleteConfirmationDialog from '../DeleteConfirmationDialog';

import { IProductAdmin } from '../../../../../../../types/products/interfaces';
import PutInStockPopup from '../../../PutInStockPopup';

export interface ProductsMenuPopupProps {
  product: IProductAdmin;
  refresh?: () => Promise<void>;
  setProducts?: Dispatch<SetStateAction<IProductAdmin[]>>;
}

const ProductsMenuPopup: FC<ProductsMenuPopupProps> = ({
  product,
  refresh,
  setProducts,
}) => {
  const navigate = useNavigate();
  const [menuAnchorEl, setMenuAnchorEl] = useState<HTMLElement | null>(null);
  const [putInStockOpen, setPutInStockOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const deleteToastAnchorEl = useRef<HTMLDivElement>(null);

  const changeStockCount = (newCount: number) => {
    setProducts?.(prev =>
      prev.map(p => {
        if (p.id === product.id) {
          return { ...p, totalQuantity: newCount + p.totalQuantity };
        }
        return p;
      })
    );
  };

  const handleEditProduct = () =>
    navigate(`/admin/products/edit/${product.id}`);

  const handleDuplicateProduct = () =>
    navigate(`/admin/products/add?duplicateId=${product.id}`);

  const handlePutInStock = () => setPutInStockOpen(true);

  const handlePreviewProduct = () => {
    navigate(`/admin/products/preview/${product.id}`);
  };

  const handleDeleteProduct = () => {
    setDeleteDialogOpen(true);
  };

  const confirmDeleteProduct = () => {
    if (product.isPublished) {
      return;
    }
    setIsLoading(true);
    deleteProduct(product.id)
      .then(() => {
        showToast({
          message: 'Product deleted successfully',
          type: 'success',
          anchorEl: deleteToastAnchorEl.current,
          autoClose: 1000,
          style: {
            boxShadow: 'none',
          },
          onClose: () => {
            setDeleteDialogOpen(false);
            setIsLoading(false);
            refresh?.();
          },
        });
      })
      .catch(error => {
        console.error('Error deleting product:', error);
        setDeleteDialogOpen(false);
        setIsLoading(false);
        // toast.error('Error deleting product');
      });
  };

  const menuOptions: MenuItem[] = [
    {
      label: 'Edit',
      onClick: handleEditProduct,
      startComponent: (
        <IconWrapper>
          <CreateOutlinedIcon />
        </IconWrapper>
      ),
    },
    {
      label: 'Duplicate the product',
      onClick: handleDuplicateProduct,
      startComponent: (
        <IconWrapper>
          <ContentCopyOutlinedIcon />
        </IconWrapper>
      ),
    },
    {
      label: 'Put in stock',
      onClick: handlePutInStock,
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
      disabled: product.isPublished,
      startComponent: (
        <IconWrapper>
          <DeleteOutlineOutlinedIcon />
        </IconWrapper>
      ),
    },
  ];

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setMenuAnchorEl(e.currentTarget as HTMLElement);
  };

  return (
    <div onClick={handleClick}>
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
        <IconButton sx={IconButtonStyle} aria-label="product-actions">
          <MoreHorizIcon fontSize="small" />
        </IconButton>
      </MenuPopup>

      <PutInStockPopup
        open={putInStockOpen}
        anchorEl={menuAnchorEl}
        onClose={() => setPutInStockOpen(false)}
        onConfirm={changeStockCount}
        product={product}
      />

      <DeleteConfirmationDialog
        toastRef={deleteToastAnchorEl}
        open={deleteDialogOpen}
        product={product}
        onClose={() => setDeleteDialogOpen(false)}
        onConfirm={confirmDeleteProduct}
        isLoading={isLoading}
      />
    </div>
  );
};

export default ProductsMenuPopup;
