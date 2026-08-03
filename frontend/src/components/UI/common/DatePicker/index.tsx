import { ChangeEvent, FC, useState } from 'react';

import dayjs, { Dayjs } from 'dayjs';
import { DateRange, OnSelectHandler } from 'react-day-picker';

import 'react-day-picker/dist/style.css';

import { PopoverChildProps } from '../SimplePopover';

import ButtonAdmin from '../../admin/ButtonAdmin';

import CaptionLabel from './CaptionLabel';
import {
  ButtonsContainer,
  Container,
  CustomDatePicker,
  DateInput,
  InputsContainer,
  PresetButton,
  PresetsWrapper,
} from './styles';

type Preset = 'custom' | 'lastWeek' | 'lastMonth' | 'last3Months';

const dateFormat = 'MM/DD/YYYY';

const defaultRange = { from: null, to: null };

interface DatePickerProps extends PopoverChildProps {
  /** Function to be called when user clicks Save button */
  onChange: (range: { from: Dayjs; to: Dayjs }) => void;
  /** Initial value for the date range */
  value?: { from: Dayjs; to: Dayjs } | null;
}

/** Date Picker component for picking range of dates */
const DatePicker: FC<DatePickerProps> = ({
  onChange,
  onRequestClose,
  value,
}) => {
  const [range, setRange] = useState<{ from: Dayjs | null; to: Dayjs | null }>(
    value || defaultRange
  );
  const [preset, setPreset] = useState<Preset>('custom');
  const [inputs, setInputs] = useState({
    from: value?.from.format(dateFormat) || '',
    to: value?.to.format(dateFormat) || '',
  });

  const handlePreset = (newPreset: Preset) => {
    return () => {
      if (!newPreset) return;
      setPreset(newPreset);

      const today = dayjs();
      let from: Dayjs, to: Dayjs;
      switch (newPreset) {
        case 'lastWeek':
          from = today.subtract(1, 'week').startOf('week').add(1, 'day');
          to = today.subtract(1, 'week').endOf('week').add(1, 'day');
          break;
        case 'lastMonth':
          from = today.subtract(1, 'month').startOf('month');
          to = today.subtract(1, 'month').endOf('month');
          break;
        case 'last3Months':
          from = today.subtract(3, 'month').startOf('month');
          to = today.subtract(1, 'month').endOf('month');
          break;
        default:
          return;
      }
      setRange({ from, to });
      setInputs({
        from: from.format(dateFormat),
        to: to.format(dateFormat),
      });
    };
  };

  const handleSelect: OnSelectHandler<DateRange | undefined> = selection => {
    const { from, to } = selection as DateRange;
    setRange({
      from: from ? dayjs(from) : null,
      to: to ? dayjs(to) : null,
    });
    setPreset('custom');
    setInputs({
      from: from ? dayjs(from).format(dateFormat) : '',
      to: to ? dayjs(to).format(dateFormat) : '',
    });
  };

  const handleInputChange = (side: 'from' | 'to') => {
    return (e: ChangeEvent<HTMLInputElement>) => {
      const val = e.target.value;
      setInputs(prev => ({ ...prev, [side]: val }));
    };
  };

  const handleInputBlur = (side: 'from' | 'to') => {
    return () => {
      const parsed = dayjs(inputs[side], dateFormat, true);
      if (!parsed.isValid()) {
        // revert to last known good
        setInputs({
          from: range.from?.format(dateFormat) ?? '',
          to: range.to?.format(dateFormat) ?? '',
        });
        return;
      }
      setRange(prev => ({
        ...prev,
        [side]: parsed,
      }));
      setPreset('custom');
    };
  };

  const handleClear = () => {
    setRange(defaultRange);
    setInputs({ from: '', to: '' });
    setPreset('custom');
  };
  const handleSave = () => {
    const { from, to } = range;
    if (from && to) {
      onChange({ from, to });
      onRequestClose?.();
    }
  };

  return (
    <Container>
      <CustomDatePicker
        animate
        mode="range"
        selected={{
          from: range.from?.toDate() ?? undefined,
          to: range.to?.toDate() ?? undefined,
        }}
        onSelect={handleSelect}
        pagedNavigation
        fixedWeeks
        showOutsideDays
        hideNavigation
        components={{
          CaptionLabel,
        }}
      />

      <PresetsWrapper>
        <PresetButton
          disabled={preset === 'custom'}
          onClick={handlePreset('custom')}
        >
          Custom
        </PresetButton>
        <PresetButton
          disabled={preset === 'lastWeek'}
          onClick={handlePreset('lastWeek')}
        >
          Last week
        </PresetButton>
        <PresetButton
          disabled={preset === 'lastMonth'}
          onClick={handlePreset('lastMonth')}
        >
          Last month
        </PresetButton>
        <PresetButton
          disabled={preset === 'last3Months'}
          onClick={handlePreset('last3Months')}
        >
          Last 3 months
        </PresetButton>
      </PresetsWrapper>

      <InputsContainer>
        <DateInput
          placeholder="mm/dd/yyyy"
          value={inputs.from}
          onChange={handleInputChange('from')}
          onBlur={handleInputBlur('from')}
        />
        <DateInput
          placeholder="mm/dd/yyyy"
          value={inputs.to}
          onChange={handleInputChange('to')}
          onBlur={handleInputBlur('to')}
        />
      </InputsContainer>

      <ButtonsContainer>
        <ButtonAdmin fullWidth variant="outlined" onClick={handleClear}>
          Clear
        </ButtonAdmin>
        <ButtonAdmin
          fullWidth
          variant="contained"
          onClick={handleSave}
          disabled={!range.from || !range.to}
        >
          Save
        </ButtonAdmin>
      </ButtonsContainer>
    </Container>
  );
};

export default DatePicker;
