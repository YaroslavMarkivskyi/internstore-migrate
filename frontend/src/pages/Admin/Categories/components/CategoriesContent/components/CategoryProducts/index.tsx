import { memo, useCallback, useEffect, useRef, useState } from 'react';

import { useDraggable } from '@dnd-kit/core';
import ClearIcon from '@mui/icons-material/Clear';
import DeleteIcon from '@mui/icons-material/Delete';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import EditIcon from '@mui/icons-material/Edit';
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import SortIcon from '@mui/icons-material/UnfoldMore';
import {
  Box,
  Button,
  Checkbox,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  FormControl,
  IconButton,
  MenuItem,
  Select,
  SelectChangeEvent,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';

import { updateCategory } from '@services/http/admin/categories';

import CategoriesInput from '../CategoriesInput';

import IOSSwitch from '../../../../../../../components/UI/admin/IOSSwitch';
import Pagination from '../../../../../../../components/UI/common/Pagination';
import { Category, Product } from '../../types';

import {
  ActionsCell,
  CategoryNameWrapper,
  CategoryProductsContainer,
  CheckboxCell,
  DragHandleCell,
  HeaderBox,
  HeaderTitle,
  PaginationWrapper,
  ProductImage,
  StyledTableRow,
  TableBox,
  TableContainer,
  TableHeadCell,
  TableHeadCellWithSort,
  TableSortButton,
} from './styles';

// Component for the product row with drag handle
const DraggableProductRow = ({
  product,
  isSelected,
  onToggleSelect,
}: {
  product: Product;
  isSelected: boolean;
  onToggleSelect: (productId: string) => void;
}) => {
  // Reference to the row element for measuring sizes
  const rowRef = useRef<HTMLTableRowElement | null>(null);

  // Single useDraggable instance per product row
  const {
    attributes,
    listeners,
    setNodeRef,
    isDragging,
    active: _active,
  } = useDraggable({
    id: `product-${product.id}`,
    // Providing product data to be accessible in DndContext events
    data: {
      product,
      type: 'product',
    },
  });

  // Row styles based on drag state
  const rowStyle = isDragging
    ? {
        opacity: 0.2, // More transparent when dragging
        backgroundColor: '#e3f2fd', // Light blue background
        borderLeft: '3px solid #2196f3', // Left border to indicate dragging state
        position: 'relative' as const, // Type assertion to make it a valid position value
        transform: 'scale(0.98)', // Slightly smaller to indicate it's being moved
        transition: 'all 0.2s ease',
      }
    : {};

  const handleRef = (element: HTMLTableRowElement | null) => {
    // Store a reference to the row element
    rowRef.current = element;

    // Pass the reference to the drag handle for the drag operation
    if (element) {
      setNodeRef(element);
    }
  };

  const handleCheckboxClick = (e: React.MouseEvent) => {
    // Prevent the row click from triggering when clicking the checkbox
    e.stopPropagation();
    onToggleSelect(product.id);
  };

  return (
    <StyledTableRow
      ref={handleRef}
      style={rowStyle}
      selected={isSelected}
      hover
    >
      <DragHandleCell>
        <Tooltip title="Drag row to move to another category">
          <span
            {...listeners}
            {...attributes}
            style={{
              cursor: isDragging ? 'grabbing' : 'grab',
              display: 'inline-flex',
              color: isDragging ? '#2196f3' : 'inherit',
              transition: 'all 0.2s ease',
            }}
          >
            <DragIndicatorIcon color={isDragging ? 'primary' : 'action'} />
          </span>
        </Tooltip>
      </DragHandleCell>
      <CheckboxCell>
        <Checkbox
          checked={isSelected}
          onClick={handleCheckboxClick}
          color="primary"
          size="small"
        />
      </CheckboxCell>
      <TableCell>{product.id}</TableCell>
      <TableCell>
        <ProductImage
          src={
            product.image ||
            'https://placehold.co/200x200/eeeeee/999999?text=No+Image'
          }
          alt={product.name}
        />
      </TableCell>
      <TableCell>{product.name}</TableCell>
      <TableCell>${parseFloat(product.price).toFixed(2)}</TableCell>
      <TableCell>
        {typeof product.totalQuantity === 'number'
          ? product.totalQuantity.toLocaleString()
          : '0'}
      </TableCell>
      <TableCell>
        <IOSSwitch
          checked={product.isPublished}
          onChange={() => {
            // TODO: Implement toggle publish functionality
          }}
        />
      </TableCell>
      <ActionsCell>
        <Tooltip title="More actions (coming soon)">
          <span>
            <IconButton
              size="small"
              sx={{
                backgroundColor: '#f5f5f5',
                '&:hover': {
                  backgroundColor: '#e0e0e0',
                },
              }}
              disabled={true}
            >
              <MoreHorizIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
      </ActionsCell>
    </StyledTableRow>
  );
};

interface CategoryProductsProps {
  category: Category;
  loading?: boolean;
  isUpdating?: boolean;
  allCategories?: Category[];
  onCategoryDeleted?: (categoryId: string) => Promise<void>;
  onCategoryUpdated?: (categoryId: string, updatedCategory: Category) => void;
  onProductsMove?: (productIds: string[], targetCategoryId: string) => void;
  onProductsDelete?: (productIds: string[]) => Promise<void>;
  pagination?: {
    currentPage: number;
    totalPages: number;
    totalItems: number;
    pageSize: number;
  };
  onPageChange?: (page: number) => void;
}

/**
 * Component to display products for a selected category.
 * Expects the category to have a products array populated. If the products
 * array is empty but loading is true, it will show a loading spinner.
 * If products array is empty and loading is false, it shows "No products in this category".
 */
const CategoryProducts = ({
  category,
  loading = false,
  isUpdating: propIsUpdating = false,
  allCategories = [],
  onCategoryDeleted,
  onCategoryUpdated,
  onProductsMove,
  onProductsDelete,
  pagination = { currentPage: 1, totalPages: 1, totalItems: 0, pageSize: 8 },
  onPageChange,
}: CategoryProductsProps) => {
  // Debug log
  console.log(
    `CategoryProducts render: category=${category.id}, name=${category.name}, loading=${loading}, products=${category?.products?.length || 0}`
  );

  const [selectedProducts, setSelectedProducts] = useState<string[]>([]);
  const [dialogState, setDialogState] = useState<
    'none' | 'deleteCategory' | 'deleteProducts' | 'moveProducts'
  >('none');
  const [isDeleting, setIsDeleting] = useState(false);
  const [isMoving, setIsMoving] = useState(false);
  const [targetCategoryId, setTargetCategoryId] = useState<string | null>(null);
  const [showEditInput, setShowEditInput] = useState(false);
  const editButtonRef = useRef<HTMLButtonElement>(null);

  // Add a ref to track the previous products count
  const prevProductsCountRef = useRef<number>(0);

  // Track if we're in an updating state (vs initial loading)
  const [internalIsUpdating, setInternalIsUpdating] = useState(false);

  // Combine prop and internal updating state
  const isUpdating = propIsUpdating || internalIsUpdating;

  // Update prevProductsCount when products change
  useEffect(() => {
    if (category.products) {
      // If we had products before but now we don't, and we're loading,
      // then we're in an updating state
      if (
        prevProductsCountRef.current > 0 &&
        category.products.length === 0 &&
        loading
      ) {
        setInternalIsUpdating(true);
      } else if (!loading) {
        // Reset the updating state when loading completes
        setInternalIsUpdating(false);
      }

      // Save the current count for the next render
      prevProductsCountRef.current = category.products.length;
    }
  }, [category.products, loading, category.id]);

  // Skip "No products" message if we previously had products and now they're gone
  // but we have a non-zero product count (meaning products exist on other pages)
  const skipNoProductsMessage =
    !loading &&
    (!category.products || category.products.length === 0) &&
    prevProductsCountRef.current > 0 &&
    (category.productCount || 0) > 0;

  // Clear selected products when category changes
  useEffect(() => {
    setSelectedProducts([]);
  }, [category.id]);

  const handleEditCategory = () => {
    setShowEditInput(true);
  };

  const handleCancelEdit = () => {
    setShowEditInput(false);
  };

  const handleSubmitEdit = async (newName: string) => {
    try {
      const updatedCategory = await updateCategory(category.id, newName);
      setShowEditInput(false);

      // Update the category in the parent component
      if (onCategoryUpdated) {
        onCategoryUpdated(category.id, updatedCategory);
      }
    } catch (error) {
      console.error('Error updating category:', error);
      throw error;
    }
  };

  const handleOpenDeleteDialog = () => {
    setDialogState('deleteCategory');
  };

  const handleCloseDialog = () => {
    setDialogState('none');
  };

  const handleDeleteCategory = async () => {
    if (!onCategoryDeleted) return;

    try {
      setIsDeleting(true);

      // Show a subtle transition effect before removing
      // by setting a small timeout to allow the dialog to close
      await onCategoryDeleted(category.id);

      // Close the dialog immediately for better UX
      handleCloseDialog();
    } catch (error) {
      console.error('Error deleting category:', error);
      // Error handling is done in the parent component
    } finally {
      // Reset deleting state after a short delay to ensure smooth transition
      setTimeout(() => {
        setIsDeleting(false);
      }, 300);
    }
  };

  const handleToggleSelect = (productId: string) => {
    setSelectedProducts(prevSelected => {
      if (prevSelected.includes(productId)) {
        return prevSelected.filter(id => id !== productId);
      } else {
        return [...prevSelected, productId];
      }
    });
  };

  const handleSelectAll = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.checked && category.products) {
      setSelectedProducts(category.products.map(product => product.id));
    } else {
      setSelectedProducts([]);
    }
  };

  const handleClearSelection = () => {
    setSelectedProducts([]);
  };

  // New functions for product deletion
  const handleOpenDeleteProductsDialog = () => {
    setDialogState('deleteProducts');
  };

  const handleDeleteSelectedProducts = useCallback(() => {
    if (!onProductsDelete || selectedProducts.length === 0) return;

    // Set deleting state for UI feedback
    setIsDeleting(true);

    // Call the parent's delete handler
    onProductsDelete(selectedProducts)
      .then(() => {
        // Clear selection and close dialog
        setSelectedProducts([]);
        setDialogState('none');
      })
      .catch(error => {
        console.error('Error when deleting products:', error);
        // Dialog will stay open if there's an error so user can try again
      })
      .finally(() => {
        setIsDeleting(false);
      });
  }, [selectedProducts, onProductsDelete]);

  // New functions for product moving
  const handleOpenMoveDialog = () => {
    setTargetCategoryId(null);
    setDialogState('moveProducts');
  };

  const handleTargetCategoryChange = (
    event: SelectChangeEvent<string>
  ) => {
    const value = event.target.value;
    setTargetCategoryId(value || null);
  };

  const handleMoveProducts = useCallback(() => {
    if (targetCategoryId !== null && onProductsMove) {
      setIsMoving(true);

      // Simulate API call
      setTimeout(() => {
        onProductsMove(selectedProducts, targetCategoryId);
        setSelectedProducts([]);
        setDialogState('none');
        setIsMoving(false);
      }, 500);
    }
  }, [targetCategoryId, selectedProducts, onProductsMove]);

  const isAllSelected =
    category.products &&
    category.products.length > 0 &&
    selectedProducts.length === category.products.length;

  // Filter out the current category from available target categories
  const availableTargetCategories = allCategories.filter(
    c => c.id !== category.id
  );

  const isMoveButtonDisabled = targetCategoryId === null || isMoving;

  // Handle pagination
  const handlePaginationChange = (
    _event: React.ChangeEvent<unknown>,
    page: number
  ) => {
    if (onPageChange && !loading) {
      onPageChange(page);
    }
  };

  // useEffect to check pagination status when category product count changes
  useEffect(() => {
    if (!category || loading) return;

    const productCount = category.productCount || 0;
    const shouldShowPagination = productCount > pagination.pageSize;

    console.log(
      `Category products changed: count=${productCount}, pageable=${shouldShowPagination}`
    );

    // If current pagination state doesn't match reality and we need to update
    const paginationMismatch =
      (shouldShowPagination && pagination.totalPages <= 1) ||
      (!shouldShowPagination && pagination.totalPages > 1);

    if (paginationMismatch && onPageChange) {
      console.log('Pagination mismatch detected, updating display');
      // Reset to page 1 when transitioning between pagination states
      onPageChange(1);
    }
  }, [category, pagination, loading, onPageChange]);

  return (
    <CategoryProductsContainer>
      <HeaderBox>
        {selectedProducts.length > 0 ? (
          <CategoryNameWrapper>
            <Box display="flex" flexDirection="column">
              <HeaderTitle>
                Products in the category "{category.name}"
              </HeaderTitle>
              <Box>{category.productCount || 0} products</Box>
            </Box>
            <Box display="flex" alignItems="center" gap={2}>
              <Box display="flex" alignItems="center">
                <ClearIcon
                  fontSize="small"
                  sx={{ mr: 1, cursor: 'pointer', color: '#818181' }}
                  onClick={handleClearSelection}
                />
                <Typography variant="body2" color="#818181">
                  {selectedProducts.length} items selected
                </Typography>
              </Box>
              <Button
                variant="outlined"
                sx={{
                  textTransform: 'none',
                  color: '#818181',
                  borderColor: '#e0e0e0',
                  borderRadius: '10px',
                  py: 0.75,
                  px: 2,
                  '&:hover': {
                    borderColor: '#d0d0d0',
                    backgroundColor: '#f9f9f9',
                  },
                }}
                onClick={handleOpenDeleteProductsDialog}
              >
                Delete
              </Button>
              <Button
                variant="outlined"
                sx={{
                  textTransform: 'none',
                  color: '#3D318E',
                  borderColor: '#e5e5ef',
                  borderRadius: '10px',
                  py: 0.75,
                  px: 2,
                  '&:hover': {
                    borderColor: '#d5d5ef',
                    backgroundColor: '#f9f9ff',
                  },
                }}
                onClick={handleOpenMoveDialog}
              >
                Move to
              </Button>
            </Box>
          </CategoryNameWrapper>
        ) : (
          <CategoryNameWrapper>
            <Box display="flex" flexDirection="column">
              <HeaderTitle>
                Products in the category "{category.name}"
              </HeaderTitle>
              <Box>{category.productCount || 0} products</Box>
            </Box>
            <Box
              display="flex"
              gap="8px"
              position="relative"
              alignItems="center"
            >
              <Button
                ref={editButtonRef}
                variant="text"
                sx={{
                  textTransform: 'none',
                  color: '#3D318E',
                }}
                onClick={handleEditCategory}
                disabled={showEditInput}
                endIcon={<EditIcon />}
              >
                Edit the name
              </Button>
              <Button
                variant="text"
                sx={{
                  textTransform: 'none',
                  color: '#818181',
                }}
                onClick={handleOpenDeleteDialog}
                endIcon={<DeleteIcon />}
              >
                Delete the category
              </Button>

              {showEditInput && (
                <CategoriesInput
                  initialValue={category.name}
                  placeholder="Enter new category name"
                  position={{
                    right: '0',
                    top: '40px',
                  }}
                  onSubmit={handleSubmitEdit}
                  onCancel={handleCancelEdit}
                />
              )}
            </Box>
          </CategoryNameWrapper>
        )}
      </HeaderBox>

      <TableBox>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <DragHandleCell>
                  <TableHeadCell>Drag</TableHeadCell>
                </DragHandleCell>
                <CheckboxCell>
                  <Checkbox
                    indeterminate={
                      selectedProducts.length > 0 && !isAllSelected
                    }
                    checked={isAllSelected}
                    onChange={handleSelectAll}
                    color="primary"
                    size="small"
                  />
                </CheckboxCell>
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
                  <TableHeadCellWithSort>
                    Price
                    <Tooltip title="Sorting coming soon">
                      <span>
                        <TableSortButton size="small" disabled>
                          <SortIcon fontSize="small" />
                        </TableSortButton>
                      </span>
                    </Tooltip>
                  </TableHeadCellWithSort>
                </TableCell>
                <TableCell>
                  <TableHeadCellWithSort>
                    Quantity
                    <Tooltip title="Sorting coming soon">
                      <span>
                        <TableSortButton size="small" disabled>
                          <SortIcon fontSize="small" />
                        </TableSortButton>
                      </span>
                    </Tooltip>
                  </TableHeadCellWithSort>
                </TableCell>
                <TableCell>
                  <TableHeadCell>Published</TableHeadCell>
                </TableCell>
                <TableCell padding="checkbox" width="48px">
                  <TableHeadCell>Actions</TableHeadCell>
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                category.products && category.products.length > 0 ? (
                  // Keep showing existing products with a loading overlay for better UX
                  <>
                    {category.products.map(product => (
                      <DraggableProductRow
                        key={`product-${product.id}-${category.id}`}
                        product={product}
                        isSelected={selectedProducts.includes(product.id)}
                        onToggleSelect={handleToggleSelect}
                      />
                    ))}
                    {/* Overlay with loading spinner */}
                    <TableRow>
                      <TableCell
                        colSpan={9}
                        sx={{
                          position: 'relative',
                          height: 0,
                          padding: 0,
                          border: 'none',
                        }}
                      >
                        <Box
                          sx={{
                            position: 'absolute',
                            top: '-150px',
                            left: 0,
                            right: 0,
                            bottom: 0,
                            backgroundColor: 'rgba(255,255,255,0.7)',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            zIndex: 5,
                          }}
                        >
                          <CircularProgress size={40} sx={{ mb: 2 }} />
                          {pagination.currentPage > 1 ? (
                            <Typography
                              variant="body2"
                              color="text.secondary"
                              sx={{
                                fontWeight: 500,
                                backgroundColor: 'white',
                                px: 2,
                                py: 1,
                                borderRadius: 1,
                              }}
                            >
                              {isUpdating
                                ? 'Updating products...'
                                : `Loading page ${pagination.currentPage}...`}
                            </Typography>
                          ) : (
                            <Typography
                              variant="body2"
                              color="text.secondary"
                              sx={{
                                fontWeight: 500,
                                backgroundColor: 'white',
                                px: 2,
                                py: 1,
                                borderRadius: 1,
                              }}
                            >
                              {isUpdating
                                ? 'Updating products...'
                                : 'Loading products...'}
                            </Typography>
                          )}
                        </Box>
                      </TableCell>
                    </TableRow>
                  </>
                ) : (
                  // Standard loading state when no products are available to show
                  <TableRow>
                    <TableCell colSpan={9} align="center" sx={{ py: 4 }}>
                      <Box
                        sx={{
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                        }}
                      >
                        <CircularProgress size={40} sx={{ mb: 2 }} />
                        {pagination.currentPage > 1 ? (
                          <Typography variant="body2" color="text.secondary">
                            {isUpdating
                              ? 'Updating products...'
                              : `Loading page ${pagination.currentPage}...`}
                          </Typography>
                        ) : (
                          <Typography variant="body2" color="text.secondary">
                            {isUpdating
                              ? 'Updating products...'
                              : 'Loading products...'}
                          </Typography>
                        )}
                      </Box>
                    </TableCell>
                  </TableRow>
                )
              ) : category.products && category.products.length > 0 ? (
                // If we have products, display them
                category.products.map(product => (
                  <DraggableProductRow
                    key={`product-${product.id}-${category.id}`}
                    product={product}
                    isSelected={selectedProducts.includes(product.id)}
                    onToggleSelect={handleToggleSelect}
                  />
                ))
              ) : skipNoProductsMessage ? (
                // Show loading instead of "No products" when we know we're just transitioning
                <TableRow>
                  <TableCell colSpan={9} align="center" sx={{ py: 4 }}>
                    <Box
                      sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                      }}
                    >
                      <CircularProgress size={40} sx={{ mb: 2 }} />
                      <Typography variant="body2" color="text.secondary">
                        Updating products...
                      </Typography>
                    </Box>
                  </TableCell>
                </TableRow>
              ) : (
                // No products to display
                <TableRow>
                  <TableCell colSpan={9} align="center" sx={{ py: 4 }}>
                    <Typography
                      variant="body1"
                      color="text.secondary"
                      sx={{ fontWeight: 500 }}
                    >
                      No products in this category
                    </Typography>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{ mt: 1 }}
                    >
                      Drag and drop products from other categories or add new
                      products.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>

        {/* 
          Pagination controls - show only when:
          1. Products count STRICTLY exceeds the page size (not just equals it)
          2. AND we verify that the category actually has products to display
        */}
        {category.products &&
        category.products.length > 0 &&
        category.productCount !== undefined &&
        category.productCount > pagination.pageSize ? (
          <PaginationWrapper>
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                width: '100%',
                gap: 3,
              }}
            >
              <Box
                sx={{
                  textAlign: 'center',
                  padding: '8px 16px',
                  backgroundColor: 'white',
                  borderRadius: '8px',
                  boxShadow: '0 2px 5px rgba(0,0,0,0.08)',
                  display: 'inline-block',
                  border: '1px solid #f0f0f0',
                  marginTop: '20px',
                }}
              >
                <Pagination
                  count={
                    pagination.totalPages ||
                    Math.ceil(
                      (category.productCount || 0) / pagination.pageSize
                    )
                  }
                  page={pagination.currentPage}
                  onChange={handlePaginationChange}
                  disabled={loading}
                />
              </Box>

              <Typography
                variant="body2"
                color="text.secondary"
                sx={{
                  textAlign: 'center',
                  marginTop: '12px',
                  fontSize: '13px',
                  opacity: 0.9,
                }}
              >
                Showing products{' '}
                {(pagination.currentPage - 1) * pagination.pageSize + 1} -{' '}
                {Math.min(
                  pagination.currentPage * pagination.pageSize,
                  pagination.totalItems || category.productCount || 0
                )}{' '}
                of {pagination.totalItems || category.productCount || 0}
              </Typography>
            </Box>
          </PaginationWrapper>
        ) : null}
      </TableBox>

      {/* Delete Category Confirmation Dialog */}
      <Dialog
        open={dialogState === 'deleteCategory' && selectedProducts.length === 0}
        onClose={handleCloseDialog}
        aria-labelledby="delete-category-dialog-title"
      >
        <DialogTitle
          id="delete-category-dialog-title"
          sx={{ color: '#10045C' }}
        >
          Delete Category
        </DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete the category "{category.name}"?
            {category.productCount && category.productCount > 0 ? (
              <span
                style={{ color: '#f44336', display: 'block', marginTop: '8px' }}
              >
                <strong>Warning:</strong> This category contains{' '}
                {category.productCount} products. You cannot delete a category
                that has products in it.
              </span>
            ) : (
              <span style={{ display: 'block', marginTop: '8px' }}>
                This action cannot be undone.
              </span>
            )}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={handleCloseDialog}
            color="primary"
            disabled={isDeleting}
          >
            Cancel
          </Button>
          <Button
            onClick={handleDeleteCategory}
            sx={{
              color: '#818181', // Changed color to #818181
              '&.Mui-disabled': {
                color: 'rgba(129, 129, 129, 0.5)', // Lighter version of #818181 when disabled
              },
            }}
            disabled={
              isDeleting ||
              !!(category.productCount && category.productCount > 0)
            }
            endIcon={!isDeleting ? <DeleteIcon /> : null}
          >
            {isDeleting ? (
              <>
                <CircularProgress size={20} sx={{ mr: 1 }} /> Deleting...
              </>
            ) : (
              'Delete'
            )}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Products Confirmation Dialog */}
      <Dialog
        open={dialogState === 'deleteProducts' && selectedProducts.length > 0}
        onClose={!isDeleting ? handleCloseDialog : undefined}
        aria-labelledby="delete-products-dialog-title"
        PaperProps={{
          sx: {
            width: '420px',
            maxWidth: '95vw',
            borderRadius: '10px',
            p: 0,
            m: 0,
          },
        }}
      >
        <Box sx={{ p: 3, pb: 2 }}>
          <Typography variant="h6" fontWeight={500} mb={2}>
            Delete Products
          </Typography>
          <Box>
            <Typography variant="body1" fontWeight={600} gutterBottom>
              {selectedProducts.length} items selected
            </Typography>
            <Typography variant="body2" mb={1}>
              Are you sure you would like to delete these items?
            </Typography>
            <Typography variant="body2" color="error.main">
              This action cannot be undone.
            </Typography>
            {isDeleting && (
              <Box
                sx={{ display: 'flex', alignItems: 'center', mt: 2, gap: 2 }}
              >
                <CircularProgress size={20} />
                <Typography variant="body2">Deleting products...</Typography>
              </Box>
            )}
          </Box>
        </Box>
        <DialogActions
          sx={{
            p: 2,
            m: 0,
            borderTop: '1px solid #e0e0e0',
            justifyContent: 'space-between',
            gap: 2,
          }}
        >
          <Button
            onClick={handleCloseDialog}
            sx={{
              flex: 1,
              py: 1.5,
              borderRadius: '10px',
              color: '#000000',
              textTransform: 'none',
              fontWeight: 500,
              border: '1px solid #e0e0e0',
            }}
            disabled={isDeleting}
          >
            No
          </Button>
          <Button
            onClick={handleDeleteSelectedProducts}
            disabled={isDeleting}
            sx={{
              flex: 1,
              py: 1.5,
              borderRadius: '10px',
              bgcolor: '#fff0f0',
              color: '#d32f2f',
              textTransform: 'none',
              fontWeight: 500,
              border: '1px solid #ffcccc',
              '&:hover': {
                bgcolor: '#ffe0e0',
              },
              '&.Mui-disabled': {
                bgcolor: '#f8f8f8',
                color: 'rgba(0, 0, 0, 0.26)',
              },
            }}
          >
            {isDeleting ? (
              <>
                <CircularProgress size={20} sx={{ mr: 1 }} /> Deleting...
              </>
            ) : (
              'Yes'
            )}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Move Products Dialog */}
      <Dialog
        open={dialogState === 'moveProducts'}
        onClose={handleCloseDialog}
        aria-labelledby="move-products-dialog-title"
        PaperProps={{
          sx: {
            width: '420px',
            maxWidth: '95vw',
            borderRadius: '10px',
            p: 0,
            m: 0,
          },
        }}
      >
        <Box sx={{ p: 3, pb: 2 }}>
          <Box display="flex" flexDirection="column" alignItems="center" mb={2}>
            <Typography variant="h6" fontWeight={500} textAlign="center">
              {selectedProducts.length} items selected
            </Typography>
            <IconButton
              onClick={handleCloseDialog}
              size="small"
              sx={{
                color: '#757575',
                '&:hover': { color: '#000000' },
                position: 'absolute',
                top: 12,
                right: 12,
              }}
            >
              <ClearIcon fontSize="small" />
            </IconButton>
          </Box>

          <Box mb={3}>
            <Typography variant="body1" mb={1}>
              Move to
            </Typography>
            <FormControl fullWidth variant="outlined">
              <Select
                id="target-category-select"
                value={targetCategoryId?.toString() || ''}
                onChange={handleTargetCategoryChange}
                displayEmpty
                renderValue={selected => {
                  if (selected === '') {
                    return (
                      <Typography sx={{ color: '#757575' }}>
                        Select a category
                      </Typography>
                    );
                  }

                  const selectedCategory = availableTargetCategories.find(
                    c => c.id === selected
                  );
                  return selectedCategory ? selectedCategory.name : '';
                }}
                sx={{
                  height: '50px',
                  borderRadius: '10px',
                }}
              >
                {availableTargetCategories.map(cat => (
                  <MenuItem key={cat.id} value={cat.id}>
                    {cat.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
        </Box>

        <DialogActions
          sx={{
            p: 2,
            m: 0,
            borderTop: '1px solid #e0e0e0',
            justifyContent: 'space-between',
            gap: 2,
          }}
        >
          <Button
            onClick={handleCloseDialog}
            sx={{
              flex: 1,
              py: 1.5,
              borderRadius: '10px',
              color: '#000000',
              textTransform: 'none',
              fontWeight: 500,
              border: '1px solid #e0e0e0',
            }}
          >
            Cancel
          </Button>
          <Button
            onClick={handleMoveProducts}
            disabled={isMoveButtonDisabled}
            sx={{
              flex: 1,
              py: 1.5,
              borderRadius: '10px',
              bgcolor: isMoveButtonDisabled ? '#e0e0e0' : '#f5f5fa',
              color: isMoveButtonDisabled ? '#757575' : '#3D318E',
              textTransform: 'none',
              fontWeight: 500,
              border: isMoveButtonDisabled
                ? '1px solid #e0e0e0'
                : '1px solid #e5e5ef',
              '&:hover': {
                bgcolor: isMoveButtonDisabled ? '#e0e0e0' : '#eeeef5',
              },
            }}
          >
            {isMoving ? 'Moving...' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>
    </CategoryProductsContainer>
  );
};

export default memo(CategoryProducts);
