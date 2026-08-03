import { ChangeEvent, FC, memo } from 'react';

import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import { Box, capitalize, Checkbox, Typography } from '@mui/material';
import { Dayjs } from 'dayjs';

import IOSSwitch from '@components/UI/admin/IOSSwitch';
import SelectFieldAdmin from '@components/UI/admin/SelectFieldAdmin';
import DatePicker from '@components/UI/common/DatePicker';
import OrderStatusComponent from '@components/UI/common/OrderStatus';
import SimplePopover from '@components/UI/common/SimplePopover';
import Tag from '@components/UI/common/Tag';
import colors from '@constants/colors';

import { IOrdersFilterParamsAdmin } from '../../../../../types/orders/interfaces';
import { OrderStatus } from '../../../../../types/orders/types';

import {
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

const statuses: OrderStatus[] = [
  'new',
  'pending',
  'paid',
  'cancelled',
  'rejected',
  'done',
];

const createCheckboxOptions = (
  options: OrderStatus[],
  selectedValues: string[]
) =>
  options.map(option => ({
    value: option,
    label: '',
    startComponent: <OrderStatusComponent status={option} />,
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

interface OrdersFiltersProps
  extends Omit<
    IOrdersFilterParamsAdmin,
    'ordering' | 'page' | 'limit' | 'offset'
  > {
  setFilters: (filters: IOrdersFilterParamsAdmin) => void;
  deleteFilter: (...keys: (keyof IOrdersFilterParamsAdmin)[]) => void;
}

const OrdersFilters: FC<OrdersFiltersProps> = ({
  setFilters,
  deleteFilter,
  status: selectedStatuses,
  archived: isArchived,
  date: dateRanges,
}) => {
  const statusOptions = createCheckboxOptions(statuses, selectedStatuses ?? []);

  const handleStatusChange = (
    e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    setFilters({ status: e.target.value as unknown as OrderStatus[] });
  };

  const handleRemoveStatus = (statusToRemove: string) => {
    if (!selectedStatuses) return;
    const newStatuses = selectedStatuses.filter(s => s !== statusToRemove);
    if (newStatuses.length > 0) {
      setFilters({ status: newStatuses });
    } else {
      deleteFilter('status');
    }
  };

  const handleDateRangeChange = (range: { from: Dayjs; to: Dayjs }) => {
    setFilters({ date: [...(dateRanges ?? []), range] });
  };

  const handleRemoveDateRange = (indexToRemove: number) => {
    if (!dateRanges) return;
    const newDates = dateRanges.filter((_, index) => index !== indexToRemove);
    if (newDates.length > 0) {
      setFilters({ date: newDates });
    } else {
      deleteFilter('date');
    }
  };

  const formatDateRange = (range: { from: Dayjs; to: Dayjs }) => {
    return `${range.from.format('MM/DD/YYYY')} - ${range.to.format('MM/DD/YYYY')}`;
  };

  return (
    <FilterContainer>
      <FiltersRow>
        <FiltersGroup>
          <FilterBox>
            <SimplePopover
              trigger={
                <FilterTriggerBox>
                  <FilterLabel>Date</FilterLabel>
                  <ArrowIcon>
                    <KeyboardArrowDownIcon />
                  </ArrowIcon>
                </FilterTriggerBox>
              }
              anchorOrigin={PopoverAnchorOrigin}
              transformOrigin={PopoverTransformOrigin}
            >
              <DatePicker onChange={handleDateRangeChange} />
            </SimplePopover>
          </FilterBox>
          <FilterBox>
            <SelectFieldAdmin
              label="Status"
              name="status"
              options={statusOptions}
              value={selectedStatuses ?? []}
              onChange={handleStatusChange}
              multiple
              fullWidth
              sx={SelectFieldStyle}
            />
          </FilterBox>
        </FiltersGroup>

        <Box display="flex" flexDirection="row" alignItems="center" gap={2}>
          <Typography>Archived</Typography>
          <IOSSwitch
            checked={isArchived}
            onChange={e => setFilters({ archived: e.target.checked })}
          />
        </Box>
      </FiltersRow>

      <TagsContainer>
        <TagsWrapper>
          {selectedStatuses?.map(status => (
            <Tag
              key={`status-${status}`}
              onCloseClick={() => handleRemoveStatus(status)}
            >
              {capitalize(status)}
            </Tag>
          ))}
          {dateRanges?.map((range, index) => (
            <Tag
              key={`date-range-${index}`}
              onCloseClick={() => handleRemoveDateRange(index)}
            >
              {formatDateRange(range)}
            </Tag>
          ))}
        </TagsWrapper>
      </TagsContainer>
    </FilterContainer>
  );
};

export default memo(OrdersFilters);
