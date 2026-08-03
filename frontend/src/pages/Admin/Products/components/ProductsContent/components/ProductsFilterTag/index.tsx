import { memo } from 'react';

import Tag from '@components/UI/common/Tag';

interface FilterTagProps {
  label: string;
  onRemove: () => void;
}

const FilterTag = ({ label, onRemove }: FilterTagProps) => {
  return (
    <Tag key={`filter-${label}`} onCloseClick={onRemove}>
      {label}
    </Tag>
  );
};

export default memo(FilterTag);
