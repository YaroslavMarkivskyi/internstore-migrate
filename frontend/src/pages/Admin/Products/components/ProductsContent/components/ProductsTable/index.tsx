import { Dispatch, memo, SetStateAction } from 'react';

import SwapVertIcon from '@mui/icons-material/SwapVert';
import {
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
} from '@mui/material';

import { isAxiosError } from 'axios';

import IOSSwitch from '@components/UI/admin/IOSSwitch';
import colors from '@constants/colors';
import { imagePlaceholderUrl } from '@constants/urls';
import { toggleProductPublish } from '@services/http/admin/products';
import showToast from '@utils/showToast';

import ProductsMenuPopup from '../ProductsMenuPopup';

import { IProductAdmin } from '../../../../../../../types/products/interfaces';
import { ProductOrderingPositive } from '../../../../../../../types/products/types';

import {
  ActionsCell,
  ProductImage,
  ProductNameCell,
  StyledTableRow,
  TableBox,
  TableContainer,
  TableHeadCell,
  TableHeadCellWithSort,
  TableSortButton,
} from './styles';

interface ProductsTableProps {
  products: IProductAdmin[];
  setOrdering?: (ordering: ProductOrderingPositive) => void;
  isLoading?: boolean;
  refresh?: () => Promise<void>;
  setProducts: Dispatch<SetStateAction<IProductAdmin[]>>;
}

const ProductsTable = ({
  products,
  setOrdering,
  isLoading,
  setProducts,
  refresh,
}: ProductsTableProps) => {
  const handlePublishToggle = (id: string) => {
    const existing = products.find(product => product.id === id);
    if (!existing) {
      return;
    }
    // Same rule the backend enforces (update_product, catalog) --
    // checked here too so the switch doesn't even flash a false "on"
    // before the request round-trips and reverts it.
    if (!existing.isPublished && existing.totalQuantity <= 0) {
      showToast({
        message: 'Cannot publish a product with no stock in any warehouse',
        type: 'error',
      });
      return;
    }
    const data = { isPublished: !existing.isPublished };
    toggleProductPublish(id, data)
      .then(() => {
        setProducts(prev =>
          prev.map(product => {
            if (product.id === id) {
              return {
                ...product,
                isPublished: !product.isPublished,
              };
            }
            return product;
          })
        );
      })
      .catch(error => {
        const detail = isAxiosError(error)
          ? (error.response?.data as { detail?: string } | undefined)?.detail
          : undefined;
        showToast({
          message: detail ?? 'Error toggling publish status',
          type: 'error',
        });
      });
  };

  return (
    <TableBox>
      <TableContainer>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>
                <TableHeadCell>ID</TableHeadCell>
              </TableCell>
              <TableCell>
                <TableHeadCell>Image</TableHeadCell>
              </TableCell>
              <TableCell>
                <TableHeadCell>Name</TableHeadCell>
              </TableCell>
              <TableCell>
                <TableHeadCell>Category</TableHeadCell>
              </TableCell>
              <TableCell>
                <TableHeadCellWithSort>
                  Price
                  <TableSortButton
                    size="small"
                    data-testid="sort-price"
                    onClick={() => setOrdering?.('price')}
                  >
                    <SwapVertIcon />
                  </TableSortButton>
                </TableHeadCellWithSort>
              </TableCell>
              <TableCell>
                <TableHeadCellWithSort>
                  Quantity
                  <TableSortButton
                    size="small"
                    data-testid="sort-quantity"
                    onClick={() => setOrdering?.('total_quantity')}
                  >
                    <SwapVertIcon />
                  </TableSortButton>
                </TableHeadCellWithSort>
              </TableCell>
              <TableCell>
                <TableHeadCell>Published</TableHeadCell>
              </TableCell>
              <ActionsCell></ActionsCell>
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
              products.map(product => (
                <StyledTableRow key={product.id}>
                  <TableCell>{product.id}</TableCell>
                  <TableCell>
                    <ProductImage
                      src={product.image || imagePlaceholderUrl}
                      alt={product.name}
                    />
                  </TableCell>
                  <TableCell>
                    <ProductNameCell>{product.name}</ProductNameCell>
                  </TableCell>
                  <TableCell>
                    {product.category && product.category.name}
                  </TableCell>
                  <TableCell>{product.price}</TableCell>
                  <TableCell>{product.totalQuantity}</TableCell>
                  <TableCell>
                    <Tooltip
                      title={
                        !product.isPublished && product.totalQuantity <= 0
                          ? 'No stock in any warehouse — add stock before publishing'
                          : ''
                      }
                    >
                      <span>
                        <IOSSwitch
                          checked={product.isPublished}
                          disabled={
                            !product.isPublished && product.totalQuantity <= 0
                          }
                          onChange={() => handlePublishToggle(product.id)}
                        />
                      </span>
                    </Tooltip>
                  </TableCell>
                  <ActionsCell>
                    <ProductsMenuPopup
                      product={product as IProductAdmin}
                      refresh={refresh}
                      setProducts={setProducts}
                    />
                  </ActionsCell>
                </StyledTableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </TableBox>
  );
};

export default memo(ProductsTable);
