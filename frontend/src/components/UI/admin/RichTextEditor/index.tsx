import { ChangeEvent, ChangeEventHandler, FC, useEffect, useRef } from 'react';

import FormatBoldIcon from '@mui/icons-material/FormatBold';
import FormatItalicIcon from '@mui/icons-material/FormatItalic';
import FormatListBulletedIcon from '@mui/icons-material/FormatListBulleted';
import FormatListNumberedIcon from '@mui/icons-material/FormatListNumbered';
import FormatUnderlinedIcon from '@mui/icons-material/FormatUnderlined';
import Quill from 'quill';

import {
  ControlsContainer,
  EditArea,
  IconButtonContainer,
  Wrapper,
} from './styles';

export interface RichTextEditorProps {
  value?: unknown;
  onChange?: ChangeEventHandler<HTMLInputElement | HTMLTextAreaElement>;
}

/** Rich Text Editor Component for Admin UI Kit */
const RichTextEditor: FC<RichTextEditorProps> = ({ value, onChange }) => {
  const editorRef = useRef<HTMLDivElement>(null);
  const quillRef = useRef<Quill | null>(null);

  useEffect(() => {
    if (editorRef.current && !quillRef.current) {
      quillRef.current = new Quill(editorRef.current, {
        modules: {
          toolbar: false,
        },
      });

      quillRef.current.on('text-change', () => {
        const html = quillRef.current?.root.innerHTML ?? '';
        const event = {
          target: { value: html },
        } as ChangeEvent<HTMLInputElement>;
        onChange?.(event);
      });
    }
  }, [onChange]);

  useEffect(() => {
    if (quillRef.current && value !== undefined) {
      const currentContent = quillRef.current.root.innerHTML;
      if (currentContent !== value) {
        if (typeof value === 'string') {
          quillRef.current.root.innerHTML = value;
        }
      }
    }
  }, [value]);

  const format = (command: string) => {
    const quill = quillRef.current;
    if (!quill) return;

    const range = quill.getSelection();
    if (!range) return;

    if (command === 'header') {
      const currentFormat = quill.getFormat(range);
      const isActive = currentFormat.header === 2;
      quill.format('header', isActive ? false : 2);
    } else {
      const currentFormat = quill.getFormat(range);
      const isActive = currentFormat[command] === true;
      quill.format(command, !isActive);
    }
  };

  const formatList = (type: 'ordered' | 'bullet') => {
    const quill = quillRef.current;
    if (!quill) return;

    const range = quill.getSelection();
    if (!range) return;

    const currentFormat = quill.getFormat(range);
    const isActive = currentFormat.list === type;
    quill.format('list', isActive ? false : type);
  };

  return (
    <Wrapper>
      <EditArea ref={editorRef} />
      <ControlsContainer>
        <IconButtonContainer onClick={() => format('bold')}>
          <FormatBoldIcon color="inherit" />
        </IconButtonContainer>
        <IconButtonContainer onClick={() => format('italic')}>
          <FormatItalicIcon color="inherit" />
        </IconButtonContainer>
        <IconButtonContainer onClick={() => format('underline')}>
          <FormatUnderlinedIcon color="inherit" />
        </IconButtonContainer>
        <IconButtonContainer onClick={() => format('header')}>
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M11.2191 19.2168V5.49762H9.374V11.3067H2.59653V5.49909H0.75V19.2168H2.59507V12.9358H9.37107V19.2168H11.2191ZM15.6513 9.31741V9.24683C15.6513 7.93975 16.5753 6.79441 18.1681 6.79441C19.5717 6.79441 20.6248 7.68834 20.6248 9.10569C20.6248 10.3628 19.8123 11.317 19.0599 12.1712L13.9075 18.0509V19.2168H22.75V17.6083H16.524V17.498L20.1628 13.3166C21.4461 11.8492 22.4889 10.6936 22.4889 8.97483C22.4889 6.82381 20.7949 5.2168 18.2077 5.2168C15.3609 5.2168 13.8576 7.16639 13.8576 9.24536V9.31741H15.6513Z"
              fill="currentColor"
            />
          </svg>
        </IconButtonContainer>
        <IconButtonContainer onClick={() => formatList('ordered')}>
          <FormatListNumberedIcon color="inherit" />
        </IconButtonContainer>
        <IconButtonContainer onClick={() => formatList('bullet')}>
          <FormatListBulletedIcon color="inherit" />
        </IconButtonContainer>
      </ControlsContainer>
    </Wrapper>
  );
};

export default RichTextEditor;
