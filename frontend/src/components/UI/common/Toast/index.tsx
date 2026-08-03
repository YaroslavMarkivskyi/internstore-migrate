import { CSSProperties } from 'react';

import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import DangerousIcon from '@mui/icons-material/Dangerous';
import ErrorIcon from '@mui/icons-material/Error';
import InfoIcon from '@mui/icons-material/Info';
import { Typography } from '@mui/material';
import { ToastContentProps } from 'react-toastify';

import { ToastContainer } from '@components/UI/common/Toast/styles';
import colors from '@constants/colors';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastData {
  type: ToastType;
  message: string;
  anchorEl?: HTMLElement | null;
  style?: CSSProperties;
}

const statusMap = {
  success: {
    icon: <CheckCircleIcon style={{ color: colors.success100 }} />,
    bgColor: colors.success900,
  },
  error: {
    icon: <DangerousIcon style={{ color: colors.error100 }} />,
    bgColor: colors.error900,
  },
  warning: {
    icon: <ErrorIcon style={{ color: colors.warning100 }} />,
    bgColor: colors.warning900,
  },
  info: {
    icon: <InfoIcon style={{ color: colors.textDisabled100 }} />,
    bgColor: colors.primary.background,
  },
};

const Toast = ({ data }: ToastContentProps<ToastData>) => {
  const { type, message, anchorEl, style } = data;

  const verticalOffset = anchorEl
    ? `calc(${anchorEl.getBoundingClientRect().bottom + 8}px - var(--toastify-toast-offset))`
    : '20%';

  const horizontalOffset = anchorEl
    ? `${anchorEl.getBoundingClientRect().left + anchorEl.getBoundingClientRect().width / 2}px`
    : '0';

  const getCenteredStyles = () => {
    if (!anchorEl) {
      return {
        marginLeft: '50vw',
        transform: 'translateX(-50%)',
      };
    }
    return {
      marginTop: verticalOffset,
      marginLeft: horizontalOffset,
      transform: 'translateX(-50%)',
    };
  };

  return (
    <ToastContainer
      sx={{
        bgcolor: statusMap[type].bgColor,
        ...getCenteredStyles(),
        ...style,
      }}
    >
      <Typography>{message}</Typography>
      {statusMap[type].icon}
    </ToastContainer>
  );
};

export default Toast;
