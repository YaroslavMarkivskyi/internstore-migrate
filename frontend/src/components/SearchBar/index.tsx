import { useCallback, useState } from 'react';

import { useNavigate } from 'react-router';

import { MAX_SEARCH_RESULTS_COUNT_DROPDOWN } from '@constants/search';
import { imagePlaceholderUrl } from '@constants/urls';
import { getProducts as getProductsAdmin } from '@services/http/admin/products';
import { getProducts as getProductsCustomer } from '@services/http/public/products';
import {
  addSearchHistoryItem,
  clearSearchHistory,
  removeSearchHistoryItem,
  selectSearchHistory,
} from '@store/reducers/search';
import { AppDispatch, useDispatch, useSelector } from '@store/store';

import SearchField from '../UI/common/SearchField';

import { IProductAdmin, IProductPublic } from '../../types/products/interfaces';
import { FoundProduct, IHistoryItem } from '../../types/search/interfaces';

const castApiProductsToFoundProducts = (
  apiProducts: IProductPublic[] | IProductAdmin[],
  currentSearchTerm: string,
  dispatch: AppDispatch,
  area: 'admin' | 'customer'
): FoundProduct[] => {
  return apiProducts.map(product => ({
    id: product.id,
    name: product.name,
    highlightedName: product.highlightedName || '',
    imageSrc: product.image || imagePlaceholderUrl,
    onClick: () => {
      // Save the search term to history when product is clicked
      dispatch(
        addSearchHistoryItem({
          query: currentSearchTerm,
          area: area,
        })
      );

      console.log('navigate to product page:', product.id); // TODO: here will be redirect to product page
    },
  }));
};

interface SearchBarProps {
  area: 'admin' | 'customer';
}

export const SearchBar = ({ area }: SearchBarProps) => {
  const dispatch = useDispatch();
  const searchHistory = useSelector(selectSearchHistory(area));
  const navigate = useNavigate();

  const [foundProducts, setFoundProducts] = useState<
    FoundProduct[] | undefined
  >(undefined);
  const [foundProductsCount, setFoundProductsCount] = useState<
    number | undefined
  >(undefined);
  const [currentSearchTerm, setCurrentSearchTerm] = useState<string>('');

  // Convert search history from Redux store to the format expected by SearchField
  const historyItems: IHistoryItem[] = searchHistory.map(item => ({
    name: item.query,
    onDelete: () => handleHistoryItemDelete(item.query),
    onClick: () => handleHistoryItemClick(item.query),
  }));

  const handleHistoryItemDelete = (query: string) => {
    dispatch(removeSearchHistoryItem({ query, area: area }));
  };

  const handleHistoryItemClick = (query: string) => {
    setCurrentSearchTerm(query);
    fetchProducts(query);
    dispatch(addSearchHistoryItem({ query, area: area }));
  };

  const onHistoryClear = () => {
    dispatch(clearSearchHistory({ area: area }));
  };

  const onShowAllResultsClick = () => {
    if (currentSearchTerm.trim()) {
      dispatch(addSearchHistoryItem({ query: currentSearchTerm, area: area }));
    }
    // TODO: if area is customer, redirect to customer search results
    navigate(`products/search?search=${currentSearchTerm}`);
  };

  const fetchProducts = useCallback(
    async (value: string) => {
      setCurrentSearchTerm(value);

      if (value.trim()) {
        try {
          let paginatedResults;

          if (area === 'admin') {
            paginatedResults = await getProductsAdmin({
              highlightMatches: true,
              search: value,
              limit: MAX_SEARCH_RESULTS_COUNT_DROPDOWN,
            });
          } else {
            paginatedResults = await getProductsCustomer({
              highlightMatches: true,
              search: value,
              limit: MAX_SEARCH_RESULTS_COUNT_DROPDOWN,
            });
          }

          setFoundProductsCount(paginatedResults.count);
          setFoundProducts(
            castApiProductsToFoundProducts(
              paginatedResults.results,
              value,
              dispatch,
              area
            )
          );
        } catch (error) {
          console.error('Error fetching products:', error);
          // Clear results on error
          setFoundProductsCount(undefined);
          setFoundProducts(undefined);
        }
      } else {
        // Clear results if search is empty
        setFoundProductsCount(undefined);
        setFoundProducts(undefined);
      }
    },
    [dispatch, area]
  );

  const handleSearchSubmit = (query: string) => {
    if (query.trim()) {
      dispatch(addSearchHistoryItem({ query, area: area }));
      if (foundProductsCount && foundProductsCount > 0) {
        navigate(`products/search?search=${currentSearchTerm}`);
      }
    }
  };

  return (
    <SearchField
      count={foundProductsCount}
      maxPopupItems={MAX_SEARCH_RESULTS_COUNT_DROPDOWN}
      foundProducts={foundProducts}
      onChange={fetchProducts}
      onSubmit={handleSearchSubmit}
      onHistoryClear={onHistoryClear}
      onShowAllResultsClick={onShowAllResultsClick}
      historyItems={historyItems}
    />
  );
};
