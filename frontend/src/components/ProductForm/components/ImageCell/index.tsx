import { FC } from 'react';

import {
  DeleteContainer,
  DeleteIcon,
  EmptyImage,
  Image,
  ImageContainer,
  ImageWrapper,
} from './styles';

interface ImageCellProps {
  imageUrl?: string;
  onDelete?: () => void;
}

const ImageCell: FC<ImageCellProps> = ({ imageUrl, onDelete }) => {
  return (
    <ImageContainer>
      {imageUrl ? (
        <ImageWrapper>
          <DeleteContainer onClick={onDelete}>
            <DeleteIcon fontSize={'large'} />
          </DeleteContainer>
          <Image src={imageUrl} alt="product" />
        </ImageWrapper>
      ) : (
        <EmptyImage />
      )}
    </ImageContainer>
  );
};

export default ImageCell;
