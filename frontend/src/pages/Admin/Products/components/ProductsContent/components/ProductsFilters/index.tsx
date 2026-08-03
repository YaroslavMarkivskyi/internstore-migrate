import { ChangeEvent, FC, memo, useEffect, useMemo, useState } from 'react';

import { useNavigate } from 'react-router';

import AddIcon from '@mui/icons-material/Add';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import { Box, Checkbox, debounce } from '@mui/material';

import CategorySelect from '@components/CategorySelect';
import ButtonAdmin from '@components/UI/admin/ButtonAdmin';
import SelectFieldAdmin from '@components/UI/admin/SelectFieldAdmin';
import RangeSlider from '@components/UI/common/RangeSlider';
import SimplePopover, {
  PopoverChildProps,
} from '@components/UI/common/SimplePopover';
import colors from '@constants/colors';
import { getProductFiltersMeta } from '@services/http/admin/products';
import { selectCategories } from '@store/reducers/category';
import { useSelector } from '@store/store';

import FilterTag from '../ProductsFilterTag';

import {
  IProductFilterParamsAdmin,
  IProductFiltersMetaAdmin,
} from '../../../../../../../types/products/interfaces';
import { SelectOption } from '../../types';

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
  PublishFilterBox,
  SelectFieldStyle,
  TagsContainer,
  TagsWrapper,
} from './styles';

const FALLBACK_PRICE_RANGE = [0, 100];
const FALLBACK_QUANTITY_RANGE = [0, 100];

const publishOptions = ['Published', 'Unpublished'];

const createCheckboxOptions = (
  options: string[],
  selectedValues: string[]
): SelectOption[] =>
  options.map(option => ({
    value: option,
    label: option,
    endComponent: (
      <Checkbox
        size="small"
        checked={selectedValues.includes(option)}
        sx={{
          color: colors.text900,
          '&.Mui-checked': {
            color: colors.secondary.accent100,
          },
        }}
      />
    ),
  }));

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
    IProductFilterParamsAdmin,
    'ordering' | 'page' | 'limit' | 'offset' | 'category'
  > {
  category?: string[];
  setFilters: (filters: IProductFilterParamsAdmin) => void;
  deleteFilter: (...keys: (keyof IProductFilterParamsAdmin)[]) => void;
}

const ProductsFilters: FC<ProductsFilterProps> = ({
  setFilters,
  deleteFilter,
  isPublished,
  category,
  priceMin,
  priceMax,
  totalQuantityMin,
  totalQuantityMax,
}) => {
  const categories = useSelector(selectCategories);
  const navigate = useNavigate();

  const [filtersMeta, setFiltersMeta] = useState<IProductFiltersMetaAdmin>();

  // State for filters
  const [publishFilter, setPublishFilter] = useState<string[]>(
    isPublished !== undefined
      ? isPublished
        ? [publishOptions[0]]
        : [publishOptions[1]]
      : []
  );

  // Derived state
  const priceRange =
    priceMin !== undefined && priceMax !== undefined
      ? [priceMin, priceMax]
      : filtersMeta?.minPrice !== undefined &&
          filtersMeta.maxPrice !== undefined
        ? [filtersMeta.minPrice, filtersMeta.maxPrice]
        : FALLBACK_PRICE_RANGE;

  const quantityRange =
    totalQuantityMin !== undefined && totalQuantityMax !== undefined
      ? [totalQuantityMin, totalQuantityMax]
      : filtersMeta?.minQuantity !== undefined &&
          filtersMeta.maxQuantity !== undefined
        ? [filtersMeta.minQuantity, filtersMeta.maxQuantity]
        : FALLBACK_QUANTITY_RANGE;

  const isPriceRangeActive =
    (priceMin !== undefined && priceMin !== Number(filtersMeta?.minPrice)) ||
    (priceMax !== undefined && priceMax !== Number(filtersMeta?.maxPrice));
  const isQuantityRangeActive =
    (totalQuantityMin !== undefined &&
      totalQuantityMin !== filtersMeta?.minQuantity) ||
    (totalQuantityMax !== undefined &&
      totalQuantityMax !== filtersMeta?.maxQuantity);

  const hasActiveTags =
    (category && category.length > 0) ||
    publishFilter.length > 0 ||
    isPriceRangeActive ||
    isQuantityRangeActive;

  const publishFilterOptions = useMemo(
    () => createCheckboxOptions(publishOptions, publishFilter),
    [publishFilter]
  );

  const updateSelectedFilter = (selectedFilters: string[]) => {
    if (
      selectedFilters.length === 0 ||
      (selectedFilters.includes(publishOptions[0]) &&
        selectedFilters.includes(publishOptions[1]))
    ) {
      deleteFilter('isPublished');
    } else if (selectedFilters.includes(publishOptions[0])) {
      setFilters({ isPublished: true });
    } else {
      setFilters({ isPublished: false });
    }
  };

  const handleRemoveCategory = (categoryToDelete: string) => {
    if (!category) return;
    const newFilters = category.filter(cat => cat !== categoryToDelete);
    if (newFilters.length > 0) {
      setFilters({ category: newFilters });
    } else {
      deleteFilter('category');
    }
  };

  const handleRemovePublishOption = (option: string) => {
    setPublishFilter(prev => {
      const newFilters = prev.filter(opt => opt !== option);
      updateSelectedFilter(newFilters);
      return newFilters;
    });
  };

  const handleRemovePriceRange = () => {
    deleteFilter('priceMin', 'priceMax');
  };

  const handleRemoveQuantityRange = () => {
    deleteFilter('totalQuantityMin', 'totalQuantityMax');
  };

  const handlePriceRangeChange = debounce((range: [number, number]) => {
    setFilters({
      priceMin: range[0],
      priceMax: range[1],
    });
  }, 500);

  const handleQuantityRangeChange = debounce((range: [number, number]) => {
    setFilters({
      totalQuantityMin: range[0],
      totalQuantityMax: range[1],
    });
  }, 500);

  const handleCategoryChange = (
    e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    setFilters({
      category: e.target.value as unknown as string[],
    });
  };

  const handlePublishChange = (
    e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    let selectedFilters;
    if (Array.isArray(e.target.value)) {
      selectedFilters = e.target.value as unknown as string[];
    } else {
      selectedFilters = [e.target.value];
    }
    setPublishFilter(selectedFilters);
    updateSelectedFilter(selectedFilters);
  };

  const handleAddProductClick = () => navigate('/admin/products/add');

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

  const quantityTrigger = (
    <FilterTriggerBox>
      <FilterLabel>
        {isQuantityRangeActive
          ? `${totalQuantityMin} - ${totalQuantityMax}`
          : 'Quantity'}
      </FilterLabel>
      <ArrowIcon>
        <KeyboardArrowDownIcon />
      </ArrowIcon>
    </FilterTriggerBox>
  );

  // Render filter tags
  const renderFilterTags = () => {
    if (!hasActiveTags) return null;

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

        {isQuantityRangeActive && (
          <FilterTag
            key="quantity-range"
            label={`${totalQuantityMin} - ${totalQuantityMax}`}
            onRemove={handleRemoveQuantityRange}
          />
        )}

        {publishFilter.map(option => (
          <FilterTag
            key={`publish-${option}`}
            label={option}
            onRemove={() => handleRemovePublishOption(option)}
          />
        ))}
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

          <FilterBox>
            <SimplePopover
              trigger={quantityTrigger}
              anchorOrigin={PopoverAnchorOrigin}
              transformOrigin={PopoverTransformOrigin}
            >
              <RangeFilterContent
                value={quantityRange as [number, number]}
                onChange={handleQuantityRangeChange}
                min={filtersMeta?.minQuantity ?? FALLBACK_QUANTITY_RANGE[0]}
                max={filtersMeta?.maxQuantity ?? FALLBACK_QUANTITY_RANGE[1]}
              />
            </SimplePopover>
          </FilterBox>

          <PublishFilterBox>
            <SelectFieldAdmin
              label="Published and Unpublished"
              placeholder="All status"
              name="published"
              options={publishFilterOptions}
              value={publishFilter}
              onChange={handlePublishChange}
              multiple
              fullWidth
              sx={SelectFieldStyle}
            />
          </PublishFilterBox>
        </FiltersGroup>

        <Box>
          <ButtonAdmin
            variant="contained"
            endIcon={<AddIcon />}
            sx={AddProductButtonStyle}
            onClick={handleAddProductClick}
          >
            Add a product
          </ButtonAdmin>
        </Box>
      </FiltersRow>

      <TagsContainer>{renderFilterTags()}</TagsContainer>
    </FilterContainer>
  );
};

export default memo(ProductsFilters);
