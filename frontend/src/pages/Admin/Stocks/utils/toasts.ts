import { Bounce, toast } from 'react-toastify';

export const showErrorToast = (message: string) =>
  toast.error(message, {
    position: 'top-center',
    autoClose: 3000,
    hideProgressBar: true,
    closeOnClick: false,
    pauseOnHover: true,
    draggable: true,
    theme: 'light',
    transition: Bounce,
  });

export const SuccessToast = (message: string) => {
  toast.success(message, {
    position: 'top-center',
    autoClose: 3000,
    hideProgressBar: true,
    closeOnClick: false,
    pauseOnHover: true,
    draggable: true,
    theme: 'light',
    transition: Bounce,
  });
};
