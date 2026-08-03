import { memo, useCallback, useEffect, useRef, useState } from 'react';

import { useDraggable } from '@dnd-kit/core';
import ClearIcon from '@mui/icons-material/Clear';
import DeleteIcon from '@mui/icons-material/Delete';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import EditIcon from '@mui/icons-material/Edit';
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import MoveUpIcon from '@mui/icons-material/MoveUp';
import SwapVertIcon from '@mui/icons-material/SwapVert';
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

import {
  getCategoryProducts,
  updateCategory,
} from '@services/http/admin/categories';
import { toggleProductPublish } from '@services/http/admin/products';
import showToast from '@utils/showToast';

import CategoriesInput from '../CategoriesInput';

import IOSSwitch from '../../../../../../../../../components/UI/admin/IOSSwitch';
import Pagination from '../../../../../../../../../components/UI/common/Pagination';
import { Category, Product, ProductLoadState } from '../../../../types';

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
  onTogglePublish,
}: {
  product: Product;
  isSelected: boolean;
  onToggleSelect: (productId: string) => void;
  onTogglePublish: (productId: string) => void;
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
          onChange={() => onTogglePublish(product.id)}
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
  onCategoryDeleted?: (
    categoryId: string,
    options?: {
      deletionMode?: 'move' | 'unpublish_and_delete';
      targetCategoryId?: string;
    }
  ) => Promise<void>;
  onCategoryUpdated?: (categoryId: string, updatedCategory: Category) => void;
  onProductsMove?: (productIds: string[], targetCategoryId: string) => void;
  onProductsDelete?: (productIds: string[]) => Promise<void>;
  pagination?: {
    currentPage: number;
    totalPages: number;
    totalItems: number;
    pageSize: number;
  };
  paginationInfo?: string;
  onPageChange?: (page: number) => void;
  setCategories?: (categoryId: string, updatedProducts: Product[]) => void;
  setProductLoadState?: (categoryId: string, state: ProductLoadState) => void;
  onCategorySelect?: (category: Category) => void;
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
  paginationInfo,
  onPageChange,
  setCategories,
  setProductLoadState,
  onCategorySelect,
}: CategoryProductsProps) => {
  const [selectedProducts, setSelectedProducts] = useState<string[]>([]);
  const [dialogState, setDialogState] = useState<
    | 'none'
    | 'deleteCategory'
    | 'deleteProducts'
    | 'moveProducts'
    | 'deleteCategoryWithProducts'
  >('none');
  const [isDeleting, setIsDeleting] = useState(false);
  const [isMoving, setIsMoving] = useState(false);
  const [targetCategoryId, setTargetCategoryId] = useState<string | null>(null);
  const [showEditInput, setShowEditInput] = useState(false);
  const [deletionOption, setDeletionOption] = useState<
    'moveAll' | 'unpublishAndDeleteAll' | null
  >(null);
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

  // Add an effect to monitor product count changes
  useEffect(() => {
    // If product count drops to 0, ensure we update UI correctly
    if (category.productCount === 0 && !loading) {
      // Make sure we reset any loading or updating states
      setInternalIsUpdating(false);
    }
  }, [category.productCount, loading]);

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
    const updatedCategory = await updateCategory(category.id, newName);
    setShowEditInput(false);

    // Update the category in the parent component
    if (onCategoryUpdated) {
      onCategoryUpdated(category.id, updatedCategory);
    }
  };

  const handleOpenDeleteDialog = () => {
    // If category has products, open the special dialog
    if (category.productCount && category.productCount > 0) {
      setDialogState('deleteCategoryWithProducts');
      setDeletionOption(null);
      setTargetCategoryId(null);
    } else {
      setDialogState('deleteCategory');
    }
  };

  const handleCloseDialog = () => {
    setDialogState('none');
    setDeletionOption(null);
    setTargetCategoryId(null);
    setIsDeleting(false);
  };

  const handleDeleteCategory = async () => {
    if (!onCategoryDeleted) return;

    try {
      setIsDeleting(true);

      // Instead of calling deleteCategory directly, we'll let onCategoryDeleted handle it
      // This avoids making duplicate API calls
      await onCategoryDeleted(category.id);

      // Show success message
      showToast({
        message: `Category "${category.name}" deleted successfully`,
        type: 'success',
      });

      // Close the dialog immediately for better UX
      handleCloseDialog();
    } catch {
      // Display error message to user
      showToast({
        message: 'Failed to delete category. Please try again later.',
        type: 'error',
      });
    } finally {
      // Reset deleting state after a short delay to ensure smooth transition
      setTimeout(() => {
        setIsDeleting(false);
      }, 300);
    }
  };

  const handleDeleteWithProductsOption = (
    option: 'moveAll' | 'unpublishAndDeleteAll'
  ) => {
    setDeletionOption(option);
  };

  const handleProcessCategoryWithProducts = async () => {
    if (!deletionOption) return;

    try {
      setIsDeleting(true);

      if (deletionOption === 'unpublishAndDeleteAll') {
        // Instead of calling deleteCategory directly, we'll let onCategoryDeleted handle it
        // with the appropriate parameters to handle the unpublish_and_delete mode
        if (onCategoryDeleted) {
          // Pass the deletion mode to the onCategoryDeleted callback
          // The useCategories hook will handle the actual API call
          await onCategoryDeleted(category.id, {
            deletionMode: 'unpublish_and_delete',
          });

          // Show success message
          showToast({
            message: `Category "${category.name}" deleted successfully`,
            type: 'success',
          });
        }
      } else if (deletionOption === 'moveAll' && targetCategoryId) {
        try {
          // Get the number of products in the category being deleted
          const productsBeingMoved = category.productCount || 0;

          // Find the target category in the allCategories array
          const targetCategory = allCategories.find(
            c => c.id === targetCategoryId
          );

          if (targetCategory) {
            try {
              // Instead of calling deleteCategory directly, let onCategoryDeleted handle it
              if (onCategoryDeleted) {
                await onCategoryDeleted(category.id, {
                  deletionMode: 'move',
                  targetCategoryId: targetCategoryId,
                });

                // Fetch the updated category data from the server to get the accurate product count
                const response = await getCategoryProducts(targetCategoryId, 1);

                // Extract the updated product count and products from the response
                let updatedProductCount =
                  (targetCategory.productCount || 0) + productsBeingMoved;
                let productsData: Product[] = [];

                if (response) {
                  if ('count' in response) {
                    updatedProductCount = response.count;

                    // If response has results (paginated API), use them as products
                    if (
                      'results' in response &&
                      Array.isArray(response.results)
                    ) {
                      productsData = response.results as unknown as Product[];
                    }
                  } else if (Array.isArray(response as unknown)) {
                    // If response is an array of products
                    const responseArray = response as unknown as Product[];
                    productsData = responseArray;
                    updatedProductCount = responseArray.length;
                  }
                }

                // Create an updated category with fresh data
                const updatedCategory = {
                  ...targetCategory,
                  productCount: updatedProductCount,
                  // Include the products data so they're available immediately
                  products: productsData,
                };

                // First, mark the category as loaded to prevent another reload when we navigate
                if (setProductLoadState) {
                  setProductLoadState(
                    targetCategoryId,
                    ProductLoadState.Loaded
                  );
                }

                // Update the target category in the UI to show updated product count in the menu
                if (onCategoryUpdated) {
                  onCategoryUpdated(targetCategoryId, updatedCategory);
                }

                // Instead of trying to select the category again later, we'll do it right now
                // This will ensure the user is moved to the target category immediately
                if (onCategorySelect && updatedCategory) {
                  // Navigate to the target category where products were moved
                  onCategorySelect(updatedCategory);
                }
              }
            } catch {
              // Fallback to local calculation if server fetch fails
              const updatedCategory = {
                ...targetCategory,
                productCount:
                  (targetCategory.productCount || 0) + productsBeingMoved,
              };

              // Update the target category in the UI
              if (onCategoryUpdated) {
                onCategoryUpdated(targetCategoryId, updatedCategory);
              }
            }
          } else {
            // If we can't find the target category, just handle the basic deletion
            if (onCategoryDeleted) {
              await onCategoryDeleted(category.id);
            }
          }

          // Show success message
          showToast({
            message: `Products moved and category "${category.name}" deleted successfully`,
            type: 'success',
          });
        } catch {
          // Display error message to user
          showToast({
            message:
              'Failed to move products and delete category. Please try again later.',
            type: 'error',
          });
        }
      }

      handleCloseDialog();
    } catch {
      // Display error message to user
      showToast({
        message: 'Failed to process category deletion. Please try again later.',
        type: 'error',
      });
    } finally {
      setIsDeleting(false);
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
      .catch(() => {
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

    // If current pagination state doesn't match reality and we need to update
    const paginationMismatch =
      (shouldShowPagination && pagination.totalPages <= 1) ||
      (!shouldShowPagination && pagination.totalPages > 1);

    if (paginationMismatch && onPageChange) {
      // Reset to page 1 when transitioning between pagination states
      onPageChange(1);
    }
  }, [category, pagination, loading, onPageChange]);

  // Handler for toggling product publish state - simplified to match ProductsTable implementation exactly
  const handleTogglePublish = useCallback(
    (productId: string) => {
      // Find the product in the current category
      const existing = category.products?.find(
        product => product.id === productId
      );

      if (!existing) {
        return;
      }

      // Prepare data for the API call
      const data = {
        isPublished: !existing.isPublished,
      };

      // Call the API to toggle publish status
      toggleProductPublish(productId, data)
        .then(() => {
          // Update local state directly
          if (category.products) {
            const updatedProducts = category.products.map(product => {
              if (product.id === productId) {
                return {
                  ...product,
                  isPublished: !product.isPublished,
                };
              }
              return product;
            });

            // If direct setCategories prop is available, use it
            if (setCategories) {
              setCategories(category.id, updatedProducts);
            }
            // Otherwise fall back to onCategoryUpdated
            else if (onCategoryUpdated) {
              const updatedCategory = {
                ...category,
                products: updatedProducts,
              };
              onCategoryUpdated(category.id, updatedCategory);
            }
          }
        })
        .catch(() => {
          // Error handled by UI feedback
        });
    },
    [category, onCategoryUpdated, setCategories]
  );

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
                          <SwapVertIcon fontSize="small" />
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
                          <SwapVertIcon fontSize="small" />
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
                        onTogglePublish={handleTogglePublish}
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
                    onTogglePublish={handleTogglePublish}
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
                {paginationInfo ||
                  `Showing products ${(pagination.currentPage - 1) * pagination.pageSize + 1} - ${Math.min(
                    pagination.currentPage * pagination.pageSize,
                    pagination.totalItems || category.productCount || 0
                  )} of ${pagination.totalItems || category.productCount || 0}`}
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
            <span style={{ display: 'block', marginTop: '8px' }}>
              This action cannot be undone.
            </span>
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
              color: '#818181',
              '&.Mui-disabled': {
                color: 'rgba(129, 129, 129, 0.5)',
              },
            }}
            disabled={isDeleting}
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

      {/* New Dialog for deleting a category with products */}
      <Dialog
        open={dialogState === 'deleteCategoryWithProducts'}
        onClose={handleCloseDialog}
        aria-labelledby="delete-category-with-products-dialog-title"
        PaperProps={{
          sx: {
            width: '480px',
            maxWidth: '95vw',
            borderRadius: '10px',
          },
        }}
      >
        <DialogTitle
          id="delete-category-with-products-dialog-title"
          sx={{ color: '#10045C' }}
        >
          Category Has Published Products
        </DialogTitle>
        <DialogContent>
          <DialogContentText>
            The category "{category.name}" contains {category.productCount}{' '}
            {category.productCount === 1 ? 'product' : 'products'}
            {category.products?.some(product => product.isPublished)
              ? ', some of which are published'
              : ''}
            . To delete this category, you need to either move these products or
            unpublish and delete them.
            <span
              style={{ display: 'block', marginTop: '16px', fontWeight: 500 }}
            >
              Please choose an option:
            </span>
          </DialogContentText>

          <Box sx={{ mt: 3, mb: 2 }}>
            <Button
              fullWidth
              variant={deletionOption === 'moveAll' ? 'contained' : 'outlined'}
              color={deletionOption === 'moveAll' ? 'primary' : 'inherit'}
              sx={{
                mb: 2,
                justifyContent: 'flex-start',
                p: 2,
                borderRadius: '8px',
                textTransform: 'none',
                borderWidth: '2px',
                borderColor:
                  deletionOption === 'moveAll' ? 'primary.main' : '#e0e0e0',
                '&:hover': {
                  borderWidth: '2px',
                  borderColor:
                    deletionOption === 'moveAll' ? 'primary.dark' : '#c0c0c0',
                },
              }}
              onClick={() => handleDeleteWithProductsOption('moveAll')}
              startIcon={<MoveUpIcon />}
            >
              <Box sx={{ textAlign: 'left' }}>
                <Typography variant="body1" fontWeight={600}>
                  Move products to another category
                </Typography>
                <Typography
                  variant="body2"
                  color={
                    deletionOption === 'moveAll' ? 'white' : 'text.secondary'
                  }
                >
                  Keep the products but move them to a different category
                </Typography>
              </Box>
            </Button>

            <Button
              fullWidth
              variant={
                deletionOption === 'unpublishAndDeleteAll'
                  ? 'contained'
                  : 'outlined'
              }
              color={
                deletionOption === 'unpublishAndDeleteAll'
                  ? 'warning'
                  : 'inherit'
              }
              sx={{
                mb: 2,
                justifyContent: 'flex-start',
                p: 2,
                borderRadius: '8px',
                textTransform: 'none',
                borderWidth: '2px',
                borderColor:
                  deletionOption === 'unpublishAndDeleteAll'
                    ? 'warning.main'
                    : '#e0e0e0',
                '&:hover': {
                  borderWidth: '2px',
                  borderColor:
                    deletionOption === 'unpublishAndDeleteAll'
                      ? 'warning.dark'
                      : '#c0c0c0',
                  backgroundColor:
                    deletionOption === 'unpublishAndDeleteAll' ? '' : '#fff8f0',
                },
              }}
              onClick={() =>
                handleDeleteWithProductsOption('unpublishAndDeleteAll')
              }
              startIcon={<DeleteIcon />}
            >
              <Box sx={{ textAlign: 'left' }}>
                <Typography variant="body1" fontWeight={600}>
                  Unpublish products & delete category
                </Typography>
                <Typography
                  variant="body2"
                  color={
                    deletionOption === 'unpublishAndDeleteAll'
                      ? 'white'
                      : 'text.secondary'
                  }
                >
                  Automatically unpublish all products before deletion
                </Typography>
              </Box>
            </Button>
          </Box>

          {deletionOption === 'moveAll' && (
            <Box sx={{ mt: 3, mb: 2 }}>
              <Typography variant="body2" mb={1} fontWeight={500}>
                Select a target category:
              </Typography>
              <FormControl fullWidth variant="outlined">
                <Select
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
                    borderRadius: '8px',
                    '& .MuiOutlinedInput-notchedOutline': {
                      borderColor: '#c0c0c0',
                    },
                    '&:hover .MuiOutlinedInput-notchedOutline': {
                      borderColor: '#a0a0a0',
                    },
                    '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                      borderColor: 'primary.main',
                    },
                  }}
                >
                  {availableTargetCategories.length > 0 ? (
                    availableTargetCategories.map(cat => (
                      <MenuItem key={cat.id} value={cat.id}>
                        {cat.name}
                      </MenuItem>
                    ))
                  ) : (
                    <MenuItem disabled>No other categories available</MenuItem>
                  )}
                </Select>
              </FormControl>
              {targetCategoryId && (
                <Typography variant="body2" color="primary" mt={1}>
                  All {category.productCount}{' '}
                  {category.productCount === 1 ? 'product' : 'products'} will be
                  moved to the selected category
                </Typography>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button
            onClick={handleCloseDialog}
            color="inherit"
            disabled={isDeleting}
          >
            Cancel
          </Button>
          <Button
            onClick={handleProcessCategoryWithProducts}
            variant="contained"
            color={
              deletionOption === 'unpublishAndDeleteAll' ? 'warning' : 'primary'
            }
            disabled={
              isDeleting ||
              !deletionOption ||
              (deletionOption === 'moveAll' && !targetCategoryId)
            }
            sx={{
              minWidth: '120px',
              textTransform: 'none',
              fontWeight: 500,
            }}
          >
            {isDeleting ? (
              <>
                <CircularProgress size={20} sx={{ mr: 1 }} color="inherit" />
                {deletionOption === 'unpublishAndDeleteAll'
                  ? 'Deleting...'
                  : 'Moving...'}
              </>
            ) : deletionOption === 'unpublishAndDeleteAll' ? (
              'Unpublish & Delete'
            ) : (
              'Move & Delete'
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
