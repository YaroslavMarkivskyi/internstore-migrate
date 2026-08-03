import { ChangeEvent, FC, memo, useEffect, useState } from 'react';

import AddIcon from '@mui/icons-material/Add';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import { Box, Checkbox, debounce } from '@mui/material';

import CategorySelect from '@components/CategorySelect';
import ButtonAdmin from '@components/UI/admin/ButtonAdmin';
import RangeSlider from '@components/UI/common/RangeSlider';
import SimplePopover, {
  PopoverChildProps,
} from '@components/UI/common/SimplePopover';
import colors from '@constants/colors';
import { getProductFiltersMeta } from '@services/http/admin/products';
import { selectCategories } from '@store/reducers/category';
import { useSelector } from '@store/store';

import FilterTag from '../../../Products/components/ProductsContent/components/ProductsFilterTag';
import { useModal } from '../../hooks/ModalStockContext';

import {
  AddProductButtonStyle,
  ArrowIcon,
  FilterBox,
  FilterContainer,
  FilterLabel,
  FiltersGroup,
  FiltersRow,
  FilterTriggerBox,
  PopoverAnchorOrigin,
  PopoverTransformOrigin,
  SelectFieldStyle,
  TagsContainer,
  TagsWrapper,
} from './styles';

import { IProductFiltersMetaAdmin } from 'src/types/products/interfaces';
import { IStockProductFilterParams } from 'src/types/stocks/interfaces';

const FALLBACK_PRICE_RANGE = [0, 100];

interface RangeFilterContentProps extends PopoverChildProps {
  value: [number, number];
  onChange: (value: [number, number]) => void;
  min: number;
  max: number;
  prefix?: string;
}

const RangeFilterContent: React.FC<RangeFilterContentProps> = ({
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
    IStockProductFilterParams,
    'page' | 'limit' | 'offset' | 'category'
  > {
  category?: number[];
  setFilters: (filters: IStockProductFilterParams) => void;
  deleteFilter: (...keys: (keyof IStockProductFilterParams)[]) => void;
}

const ProductsFilters: FC<ProductsFilterProps> = ({
  setFilters,
  deleteFilter,
  category,
  priceMin,
  priceMax,
}) => {
  const categories = useSelector(selectCategories);
  const [filtersMeta, setFiltersMeta] = useState<IProductFiltersMetaAdmin>();
  const { openModal } = useModal();
  // Derived state
  const priceRange =
    priceMin !== undefined && priceMax !== undefined
      ? [priceMin, priceMax]
      : filtersMeta?.minPrice !== undefined &&
          filtersMeta.maxPrice !== undefined
        ? [filtersMeta.minPrice, filtersMeta.maxPrice]
        : FALLBACK_PRICE_RANGE;

  const isPriceRangeActive =
    (priceMin !== undefined && priceMin !== Number(filtersMeta?.minPrice)) ||
    (priceMax !== undefined && priceMax !== Number(filtersMeta?.maxPrice));

  const hasActiveTags = (category && category.length > 0) || isPriceRangeActive;

  const handleRemoveCategory = (categoryToDelete: number) => {
    if (!category) {
      return;
    }
    const newFilters = category.filter(cat => cat !== categoryToDelete);
    if (newFilters.length > 0) {
      setFilters({ category: newFilters });
    } else {
      deleteFilter('category');
    }
  };

  const handleRemovePriceRange = () => {
    deleteFilter('priceMin', 'priceMax');
  };

  const handlePriceRangeChange = debounce((range: [number, number]) => {
    setFilters({
      priceMin: range[0],
      priceMax: range[1],
    });
  }, 500);

  const handleCategoryChange = (
    e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    setFilters({
      category: e.target.value as unknown as number[],
    });
  };

  const handleAddStockClick = () => openModal({ mode: 'add' });

  const fetchFiltersMeta = async () => {
    const meta = await getProductFiltersMeta();
    setFiltersMeta(meta);
  };

  useEffect(() => {
    void fetchFiltersMeta();
  }, []);

  // Create trigger elements for SimplePopover
  const priceTrigger = (
    <FilterTriggerBox>
      <FilterLabel>
        {isPriceRangeActive ? `$${priceMin} - $${priceMax}` : 'Price'}
      </FilterLabel>
      <ArrowIcon>
        <KeyboardArrowDownIcon />
      </ArrowIcon>
    </FilterTriggerBox>
  );

  // Render filter tags
  const renderFilterTags = () => {
    if (!hasActiveTags) {
      return null;
    }

    return (
      <TagsWrapper>
        {category?.map(
          category =>
            categories[category] && (
              <FilterTag
                key={`category-${category}`}
                label={categories[category]}
                onRemove={() => handleRemoveCategory(category)}
              />
            )
        )}

        {isPriceRangeActive && (
          <FilterTag
            key="price-range"
            label={`$${priceMin} - $${priceMax}`}
            onRemove={handleRemovePriceRange}
          />
        )}
      </TagsWrapper>
    );
  };

  return (
    <FilterContainer>
      <FiltersRow>
        <FiltersGroup>
          <FilterBox>
            <CategorySelect
              label="Category"
              placeholder="All categories"
              onChange={handleCategoryChange}
              name="category"
              value={category ?? []}
              multiple
              fullWidth
              endComponent={
                <Checkbox
                  size="small"
                  sx={{
                    color: colors.text900,
                    '&.Mui-checked': {
                      color: colors.secondary.accent100,
                    },
                  }}
                />
              }
              sx={SelectFieldStyle}
            />
          </FilterBox>

          <FilterBox>
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
          </FilterBox>
        </FiltersGroup>

        <Box>
          <ButtonAdmin
            variant="contained"
            endIcon={<AddIcon />}
            sx={AddProductButtonStyle}
            onClick={handleAddStockClick}
          >
            Add a stock
          </ButtonAdmin>
        </Box>
      </FiltersRow>

      <TagsContainer>{renderFilterTags()}</TagsContainer>
    </FilterContainer>
  );
};

export default memo(ProductsFilters);
