import { memo } from 'react';

import { Box, Typography } from '@mui/material';

import { Product } from '../../../types';

import { ProductImagePreview } from './styles';

interface DraggingProductItemProps {
  product: Product;
}

/**
 * Component to render while dragging a product
 */
export const DraggingProductItem = memo(
  ({ product }: DraggingProductItemProps) => {
    return (
      <Box
        sx={{
          display: 'flex',
          padding: '16px',
          backgroundColor: '#ffffff',
          borderRadius: '8px',
          boxShadow: '0 5px 15px rgba(0,0,0,0.2)',
          width: '500px',
          border: '2px solid #2196f3',
          alignItems: 'center',
          gap: '12px',
        }}
      >
        <Box sx={{ width: '48px', display: 'flex', justifyContent: 'center' }}>
          <ProductImagePreview
            src={
              product.image ||
              'https://placehold.co/200x200/eeeeee/999999?text=No+Image'
            }
            alt={product.name}
          />
        </Box>
        <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
          <Typography
            variant="body1"
            sx={{
              fontWeight: 500,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {product.name}
          </Typography>
          <Box
            sx={{
              display: 'flex',
              gap: '12px',
              color: '#666',
              fontSize: '13px',
            }}
          >
            <Typography variant="caption">ID: {product.id}</Typography>
            <Typography variant="caption">
              Price: ${parseFloat(product.price).toFixed(2)}
            </Typography>
            <Typography variant="caption">
              Quantity: {product.totalQuantity}
            </Typography>
          </Box>
        </Box>
      </Box>
    );
  }
);
