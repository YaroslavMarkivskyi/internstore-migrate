import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react';

import { IStock } from 'src/types/stocks/interfaces';

type ModalMode = 'add' | 'edit' | 'delete';

interface OpenModalConfig {
  mode: ModalMode;
  initialData?: IStock | null;
}

interface ModalContextType {
  isOpen: boolean;
  mode: ModalMode;
  initialData: IStock | null;
  header: string;
  openModal: (config: OpenModalConfig) => void;
  closeModal: () => void;
}

const ModalContext = createContext<ModalContextType | undefined>(undefined);

export const useModal = (): ModalContextType => {
  const context = useContext(ModalContext);
  if (!context) {
    throw new Error('useModal must be used within a ModalProvider');
  }
  return context;
};

export const ModalProvider = ({ children }: { children: ReactNode }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [mode, setMode] = useState<ModalMode>('add');
  const [initialData, setInitialData] = useState<IStock | null>(null);

  const headerMap: Record<ModalMode, string> = {
    add: 'Add a stock',
    edit: 'Edit stock',
    delete: '',
  };

  const openModal = useCallback(
    ({ mode, initialData = null }: OpenModalConfig) => {
      setMode(mode);
      setInitialData(initialData);
      setIsOpen(true);
    },
    []
  );

  const closeModal = useCallback(() => {
    setIsOpen(false);
    setInitialData(null);
  }, []);

  const value = useMemo(
    () => ({
      isOpen,
      mode,
      initialData,
      header: headerMap[mode],
      openModal,
      closeModal,
    }),
    [isOpen, mode, initialData, openModal, closeModal]
  );

  return (
    <ModalContext.Provider value={value}>{children}</ModalContext.Provider>
  );
};
