import { HTMLAttributes } from 'react';

import ArrowBackIosIcon from '@mui/icons-material/ArrowBackIos';
import ArrowForwardIosIcon from '@mui/icons-material/ArrowForwardIos';
import { IconButton } from '@mui/material';
import { useDayPicker } from 'react-day-picker';

import colors from '../../../../constants/colors';

import { CaptionLabelText, CaptionLabelWrapper } from './styles';

const CaptionLabel = ({ children }: HTMLAttributes<HTMLSpanElement>) => {
  const { goToMonth, nextMonth, previousMonth } = useDayPicker();

  const goToNextMonth = () => {
    if (nextMonth) {
      goToMonth(nextMonth);
    }
  };

  const goToPreviousMonth = () => {
    if (previousMonth) {
      goToMonth(previousMonth);
    }
  };

  return (
    <CaptionLabelWrapper>
      <IconButton onClick={goToPreviousMonth}>
        <ArrowBackIosIcon fill={colors.placeholder} />
      </IconButton>
      <CaptionLabelText>{children}</CaptionLabelText>
      <IconButton onClick={goToNextMonth}>
        <ArrowForwardIosIcon fill={colors.placeholder} />
      </IconButton>
    </CaptionLabelWrapper>
  );
};

export default CaptionLabel;
