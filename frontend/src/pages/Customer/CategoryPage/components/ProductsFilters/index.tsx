import { FC, useEffect, useState } from 'react';

import CheckOutlinedIcon from '@mui/icons-material/CheckOutlined';
import FilterAltOutlinedIcon from '@mui/icons-material/FilterAltOutlined';
import SortOutlinedIcon from '@mui/icons-material/SortOutlined';
import { Box, debounce, Typography } from '@mui/material';

import MenuPopup from '@components/UI/common/MenuPopup';
import RangeSlider from '@components/UI/common/RangeSlider';
import SimplePopover, {
  PopoverChildProps,
} from '@components/UI/common/SimplePopover';
import Tag from '@components/UI/common/Tag';
import colors from '@constants/colors';
import {
  PopoverAnchorOrigin,
  PopoverTransformOrigin,
} from '@pages/Admin/Products/components/ProductsContent/components/ProductsFilters/styles';
import {
  FilterContainer,
  FiltersWrapper,
  FilterTriggerBox,
} from '@pages/Customer/CategoryPage/components/ProductsFilters/styles';
import { getProductFiltersMeta } from '@services/http/public/products';

import {
  IProductFilterParamsPublic,
  IProductFiltersMetaPublic,
} from '../../../../../types/products/interfaces';

const FALLBACK_PRICE_RANGE = [0, 100];

interface RangeFilterContentProps extends PopoverChildProps {
  value: [number, number];
  onChange: (value: [number, number]) => void;
  min: number;
  max: number;
  prefix?: string;
}

const RangeFilterContent: FC<RangeFilterContentProps> = ({
  value,
  onChange,
  prefix,
  min,
  max,
  onRequestClose: _onRequestClose,
}) => {
  return (
    <Box sx={{ p: 2, width: 400 }}>
      <RangeSlider
        min={min}
        max={max}
        defaultValue={value}
        step={1}
        prefix={prefix}
        onChange={newValue => {
          onChange(newValue as [number, number]);
        }}
      />
    </Box>
  );
};

interface ProductsFilterProps
  extends Omit<
    IProductFilterParamsPublic,
    'page' | 'limit' | 'offset' | 'category'
  > {
  setFilters: (filters: IProductFilterParamsPublic) => void;
  deleteFilter: (...keys: (keyof IProductFilterParamsPublic)[]) => void;
}

const ProductsFilters: FC<ProductsFilterProps> = ({
  priceMin,
  priceMax,
  ordering,
  setFilters,
  deleteFilter,
}) => {
  const [filtersMeta, setFiltersMeta] = useState<IProductFiltersMetaPublic>();

  const priceRange =
    priceMin !== undefined && priceMax !== undefined
      ? [priceMin, priceMax]
      : filtersMeta?.minPrice !== undefined &&
          filtersMeta.maxPrice !== undefined
        ? [filtersMeta.minPrice, filtersMeta.maxPrice]
        : FALLBACK_PRICE_RANGE;

  const handlePriceRangeChange = debounce((range: [number, number]) => {
    setFilters({
      priceMin: range[0],
      priceMax: range[1],
    });
  }, 500);

  const handlePriceRangeClear = () => {
    deleteFilter('priceMax', 'priceMin');
  };

  const fetchFiltersMeta = async () => {
    const meta = await getProductFiltersMeta();
    setFiltersMeta(meta);
  };

  useEffect(() => {
    void fetchFiltersMeta();
  }, []);

  const priceTrigger = (
    <FilterTriggerBox variant={'outlined'}>
      <FilterAltOutlinedIcon />
      <Typography>Filter by price</Typography>
    </FilterTriggerBox>
  );

  const ascendingTitle = 'Lowest to Highest';
  const descendingTitle = 'Highest to Lowest';
  const checkedComponent = (
    <CheckOutlinedIcon sx={{ color: colors.secondary.accent100 }} />
  );

  const orderingFilter = (
    <MenuPopup
      options={[
        {
          endComponent: ordering === 'price' && checkedComponent,
          label: ascendingTitle,
          onClick: () => setFilters({ ordering: 'price' }),
        },
        {
          endComponent: ordering === '-price' && checkedComponent,
          label: descendingTitle,
          onClick: () => setFilters({ ordering: '-price' }),
        },
      ]}
    >
      <FilterTriggerBox variant={'outlined'}>
        <SortOutlinedIcon />
        <Typography>
          {ordering
            ? ordering === 'price'
              ? ascendingTitle
              : descendingTitle
            : 'Sort by price'}
        </Typography>
      </FilterTriggerBox>
    </MenuPopup>
  );

  return (
    <FiltersWrapper>
      <FilterContainer>
        <SimplePopover
          trigger={priceTrigger}
          anchorOrigin={PopoverAnchorOrigin}
          transformOrigin={PopoverTransformOrigin}
        >
          <RangeFilterContent
            value={priceRange as [number, number]}
            onChange={handlePriceRangeChange}
            min={
              filtersMeta?.minPrice
                ? Number(filtersMeta.minPrice)
                : FALLBACK_PRICE_RANGE[0]
            }
            max={
              filtersMeta?.maxPrice
                ? Number(filtersMeta.maxPrice)
                : FALLBACK_PRICE_RANGE[1]
            }
            prefix="$"
          />
        </SimplePopover>
        {priceMin && priceMax && (
          <Tag onCloseClick={handlePriceRangeClear}>
            <Typography>{`From $${priceMin} to $${priceMax}`}</Typography>
          </Tag>
        )}
      </FilterContainer>
      {orderingFilter}
    </FiltersWrapper>
  );
};

export default ProductsFilters;
