import { useNavigate } from 'react-router-dom';

import EditIcon from '@mui/icons-material/Edit';
import { Stack } from '@mui/material';

import { StyledTab, StyledTabs } from './styles';

import { IStock } from 'src/types/stocks/interfaces';

interface Props {
  stocks: IStock[];
  selectedStock: number;
  onEditClick: (stock: IStock) => void;
}

export const StockTabs = ({ stocks, selectedStock, onEditClick }: Props) => {
  const navigate = useNavigate();

  const handleChange = (_: React.SyntheticEvent, newValue: number) => {
    navigate(newValue === 0 ? '/admin/stocks' : `/admin/stocks/${newValue}`);
  };

  return (
    <StyledTabs
      value={selectedStock}
      onChange={handleChange}
      aria-label="Stock selection tabs"
    >
      <StyledTab label="All Stocks" value={0} />
      {stocks.map(stock => (
        <StyledTab
          key={stock.id}
          value={stock.id}
          label={
            <Stack direction="row" alignItems="center" gap={1}>
              {stock.name}
              {stock.id === selectedStock && (
                <EditIcon
                  sx={{ fontSize: 16, ml: 0.5 }}
                  onClick={e => {
                    e.stopPropagation();
                    onEditClick(stock);
                  }}
                />
              )}
            </Stack>
          }
        />
      ))}
    </StyledTabs>
  );
};
