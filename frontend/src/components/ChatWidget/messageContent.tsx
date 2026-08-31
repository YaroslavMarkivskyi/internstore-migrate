import { Fragment, ReactNode } from 'react';

import { Link } from 'react-router-dom';

// The shopping agent is prompted to link products it mentions as
// [<name>](/products/<uuid>) (see services/ai-assistant/src/ai_assistant/
// react_loop.py). Turn those — and any bare /products/<uuid> — into
// in-app links; everything else stays plain text. Deliberately not a full
// Markdown renderer: only this one, safe, relative-path link shape.
const PRODUCT_LINK =
  /\[([^\]\n]+)\]\(\/products\/([0-9a-fA-F-]{36})\)|\/products\/([0-9a-fA-F-]{36})/g;

export const renderMessageContent = (raw: string): ReactNode => {
  // The agent is told to reply in plain prose, but strip stray leading
  // list markers ("* ", "- ") just in case a model slips one in.
  const text = raw.replace(/^[ \t]*[*-] +/gm, '');

  const parts: ReactNode[] = [];
  let cursor = 0;
  let match: RegExpExecArray | null;

  PRODUCT_LINK.lastIndex = 0;
  while ((match = PRODUCT_LINK.exec(text)) !== null) {
    if (match.index > cursor) {
      parts.push(text.slice(cursor, match.index));
    }
    const id = match[2] ?? match[3];
    const label = match[1] ?? 'View product';
    parts.push(
      <Link key={`${match.index}-${id}`} to={`/products/${id}`}>
        {label}
      </Link>
    );
    cursor = match.index + match[0].length;
  }

  if (cursor < text.length) {
    parts.push(text.slice(cursor));
  }

  return parts.length > 0
    ? parts.map((part, index) => <Fragment key={index}>{part}</Fragment>)
    : text;
};
