import sha256 from 'crypto-js/sha256';
import { Bounce, toast } from 'react-toastify';

import Toast, { ToastData } from '../components/UI/common/Toast';

interface ToastProps extends ToastData {
  position?: 'top-center' | 'bottom-center';
  onClose?: () => void;
  autoClose?: number | false;
  force?: boolean;
}

export default function showToast({
  message,
  position = 'top-center',
  type,
  autoClose = 2000,
  anchorEl,
  style,
  onClose,
  force = false,
}: ToastProps) {
  const toastId = force ? crypto.randomUUID() : sha256(message).toString();

  toast(Toast, {
    data: {
      message,
      type,
      anchorEl,
      style,
    },
    toastId,
    position,
    autoClose,
    onClose,
    hideProgressBar: true,
    closeButton: false,
    closeOnClick: false,
    pauseOnHover: false,
    draggable: false,
    progress: undefined,
    theme: 'light',
    transition: Bounce,
  });
}
