import { useMemo, useState } from 'react';

import { useNavigate } from 'react-router-dom';

import EditIcon from '@mui/icons-material/Edit';
import SearchIcon from '@mui/icons-material/Search';
import { InputAdornment, TextField } from '@mui/material';

import {
  EmptyState,
  SearchWrapper,
  SidebarContainer,
  StockItem,
  StockName,
  StyledList,
} from './styles';

import { IStock } from 'src/types/stocks/interfaces';

interface Props {
  stocks: IStock[];
  selectedStock: string;
  onEditClick: (stock: IStock) => void;
}

export const StockTabs = ({ stocks, selectedStock, onEditClick }: Props) => {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');

  const handleSelect = (stockId: string) => {
    navigate(stockId === '' ? '/admin/stocks' : `/admin/stocks/${stockId}`);
  };

  const filteredStocks = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return stocks;
    return stocks.filter(stock => stock.name.toLowerCase().includes(query));
  }, [search, stocks]);

  return (
    <SidebarContainer aria-label="Stock selection">
      <SearchWrapper>
        <TextField
          fullWidth
          size="small"
          placeholder="Search stocks"
          value={search}
          onChange={e => setSearch(e.target.value)}
          slotProps={{
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            },
          }}
        />
      </SearchWrapper>

      <StyledList>
        <StockItem
          className={selectedStock === '' ? 'selected' : ''}
          onClick={() => handleSelect('')}
        >
          <StockName sx={{ fontWeight: 600 }}>All Stocks</StockName>
        </StockItem>

        {filteredStocks.map(stock => {
          const isSelected = stock.id === selectedStock;
          return (
            <StockItem
              key={stock.id}
              className={isSelected ? 'selected' : ''}
              onClick={() => handleSelect(stock.id!)}
              title={stock.name}
            >
              {/* StockName truncates on its own (flex: 1, min-width: 0) so
                  a long name can never push the icon out of the row --
                  the icon has flex-shrink: 0 as a sibling, not squeezed
                  into the same overflow: hidden box as the text. */}
              <StockName>{stock.name}</StockName>
              {isSelected && (
                <EditIcon
                  aria-label="Edit stock"
                  sx={{ fontSize: 16, flexShrink: 0 }}
                  onClick={e => {
                    e.stopPropagation();
                    onEditClick(stock);
                  }}
                />
              )}
            </StockItem>
          );
        })}

        {filteredStocks.length === 0 && (
          <EmptyState>No stocks match "{search}"</EmptyState>
        )}
      </StyledList>
    </SidebarContainer>
  );
};
