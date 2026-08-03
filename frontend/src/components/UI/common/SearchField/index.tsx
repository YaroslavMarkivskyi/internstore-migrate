import { ChangeEvent, FC, useMemo, useRef, useState } from 'react';

import SearchIcon from '@mui/icons-material/Search';
import {
  debounce,
  InputAdornment,
  Popover,
  Stack,
  TextFieldProps,
} from '@mui/material';
import DOMPurify from 'dompurify';

import colors from '../../../../constants/colors';
import {
  FoundProduct,
  IHistoryItem,
} from '../../../../types/search/interfaces';

import {
  ButtonWrapper,
  ClearAllButton,
  FoundProductsWrapper,
  HistoryDeleteIcon,
  HistoryHeader,
  HistoryHeaderWrapper,
  HistoryItem,
  HistoryItemsWrapper,
  HistorySearchIcon,
  HistoryText,
  HistoryWrapper,
  Input,
  ItemRowWrapper,
  ItemsWrapper,
  NotFoundText,
  ProductCount,
  ProductImage,
  ProductImageWrapper,
  ProductTitle,
  SearchFieldContainer,
  ShowAllButton,
} from './styles';

interface SearchFieldProps {
  /** Debounced action to be called when search query changes. */
  onChange?: (value: string) => void;
  onSubmit?: (value: string) => void;
  /** Action to be called when "Clear All" button is pressed */
  onHistoryClear: () => void;
  /** Action to be called when "Show All Results" button is pressed */
  onShowAllResultsClick: () => void;
  /** Array of found products. Must be length of 3 */
  foundProducts?: FoundProduct[];
  /** Array of searched queries */
  historyItems?: IHistoryItem[];
  /** Count of found products with found products length */
  count?: number;
  maxPopupItems: number;
  placeholder?: string;
}

/** Search Field component to show search results on both Admin and Customer pages */
const SearchField: FC<SearchFieldProps> = ({
  onChange,
  onSubmit,
  foundProducts,
  count,
  maxPopupItems,
  historyItems,
  onHistoryClear,
  onShowAllResultsClick,
  placeholder = 'Search',
}) => {
  const [open, setOpen] = useState(false);

  const [search, setSearch] = useState('');
  const inputRef = useRef<HTMLInputElement | null>(null);
  const anchorEl = inputRef.current;
  const containerRef = useRef<HTMLDivElement | null>(null);

  const handleHistoryClick = (history: IHistoryItem) => {
    setSearch(history.name);
    onChange?.(history.name);
    history.onClick?.();
  };

  const handleKeyDown: TextFieldProps['onKeyDown'] = e => {
    if (e.key === 'Escape') {
      (e.target as HTMLInputElement).blur();
    } else if (e.key === 'Enter' && onSubmit) {
      onSubmit(search);
      (e.target as HTMLInputElement).blur();
      e.preventDefault();
    }
  };

  const debouncedOnChange = useMemo(() => {
    return debounce((value: string) => {
      onChange?.(value);
    }, 300);
  }, [onChange]);

  const handleSearchChange = (e: ChangeEvent<HTMLInputElement>) => {
    const { value } = e.target;
    setSearch(value);
    debouncedOnChange(value);
  };

  const openPopover = () => {
    setOpen(true);
  };

  const closePopover = () => {
    setOpen(false);
  };

  const handleClearAllHistory = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    onHistoryClear();

    // Focus back on the input element
    if (inputRef.current) {
      inputRef.current.focus();
    }
  };

  return (
    <SearchFieldContainer
      ref={containerRef}
      onFocus={openPopover}
      onBlur={e => {
        if (!containerRef.current?.contains(e.relatedTarget)) {
          closePopover();
        }
      }}
      tabIndex={-1}
    >
      <Input
        placeholder={placeholder}
        ref={inputRef}
        value={search}
        onChange={handleSearchChange}
        onKeyDown={handleKeyDown}
        autoComplete={'off'}
        slotProps={{
          input: {
            startAdornment: (
              <InputAdornment position="end">
                <SearchIcon fill={colors.placeholder} />
              </InputAdornment>
            ),
          },
        }}
      />
      <Popover
        open={open}
        anchorEl={anchorEl}
        disableAutoFocus
        disableEnforceFocus
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
        marginThreshold={0}
        slotProps={{
          paper: {
            sx: {
              width: inputRef.current
                ? inputRef.current.clientWidth
                : undefined,
              mt: '10px',
              boxShadow: `0px 4px 15px ${colors.border}`,
              borderRadius: '10px',
            },
          },
        }}
      >
        {search.length > 0 ? (
          foundProducts?.length ? (
            <FoundProductsWrapper>
              <ItemsWrapper>
                {foundProducts.map(product => (
                  <ItemRowWrapper key={product.id} onClick={product.onClick}>
                    <ProductImageWrapper>
                      <ProductImage
                        src={product.imageSrc}
                        alt={`${product.name} image`}
                      />
                    </ProductImageWrapper>
                    <ProductTitle
                      dangerouslySetInnerHTML={{
                        __html: DOMPurify.sanitize(
                          product.highlightedName || product.name,
                          {
                            ALLOWED_TAGS: ['b'],
                            ALLOWED_ATTR: [],
                          }
                        ),
                      }}
                    ></ProductTitle>
                  </ItemRowWrapper>
                ))}
              </ItemsWrapper>
              {count && count - foundProducts.length > 0 && (
                <ProductCount>
                  + {count - foundProducts.length} products found
                </ProductCount>
              )}
              {count && count > maxPopupItems && (
                <ButtonWrapper>
                  <ShowAllButton
                    variant="contained"
                    onClick={onShowAllResultsClick}
                  >
                    Show all results
                  </ShowAllButton>
                </ButtonWrapper>
              )}
            </FoundProductsWrapper>
          ) : (
            <NotFoundText>
              We couldn’t find the product you are looking for
            </NotFoundText>
          )
        ) : historyItems?.length ? (
          <HistoryWrapper>
            <HistoryHeaderWrapper>
              <HistoryHeader>Search history</HistoryHeader>
              <ClearAllButton
                disableRipple
                onClick={handleClearAllHistory}
                onMouseDown={e => e.preventDefault()}
              >
                Clear all
              </ClearAllButton>
            </HistoryHeaderWrapper>
            <HistoryItemsWrapper>
              {historyItems.map((historyItem, i) => (
                <HistoryItem key={i}>
                  <Stack
                    direction="row"
                    flex={1}
                    alignItems="center"
                    onClick={() => handleHistoryClick(historyItem)}
                  >
                    <HistorySearchIcon />
                    <HistoryText>{historyItem.name}</HistoryText>
                  </Stack>
                  <HistoryDeleteIcon onClick={historyItem.onDelete} />
                </HistoryItem>
              ))}
            </HistoryItemsWrapper>
          </HistoryWrapper>
        ) : (
          <NotFoundText>No items in your history</NotFoundText>
        )}
      </Popover>
    </SearchFieldContainer>
  );
};

export default SearchField;
