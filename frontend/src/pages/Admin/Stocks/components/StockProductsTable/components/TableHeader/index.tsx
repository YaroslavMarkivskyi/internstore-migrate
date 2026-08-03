import { TableCell, TableHead, TableRow } from '@mui/material';

import { ActionsCell, TableHeadCell } from './styles';

const StockTableHeader = () => (
  <TableHead>
    <TableRow>
      {[
        'ID',
        'Image',
        'Name',
        'Category',
        'Price',
        'Min t°C',
        'Max t°C',
        'Quantity',
      ].map(label => (
        <TableCell key={label}>
          <TableHeadCell>{label}</TableHeadCell>
        </TableCell>
      ))}
      <ActionsCell />
    </TableRow>
  </TableHead>
);

export default StockTableHeader;
