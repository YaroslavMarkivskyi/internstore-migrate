export type ChatSenderType = 'customer' | 'admin' | 'assistant' | 'guest';

export type ChatConnectionStatus = 'connecting' | 'open' | 'closed';

export interface ChatMessage {
  id: string;
  senderType: ChatSenderType;
  senderId: string;
  content: string;
  createdAt: string;
}

/** Server -> client frame on the `/ws/room/{room_id}` socket. */
export interface ChatHistoryFrame {
  type: 'history';
  messages: Array<{
    id: string;
    sender_type: ChatSenderType;
    sender_id: string;
    content: string | null;
    attachment_url: string | null;
    created_at: string;
  }>;
}

export interface ChatMessageFrame {
  type: 'message';
  room_id: string;
  sender_type: ChatSenderType;
  sender_id: string;
  content: string | null;
  attachment_url: string | null;
  created_at: string;
}

export interface ChatTypingFrame {
  type: 'typing';
  room_id: string;
  sender_id: string;
}

/** A piece of the assistant's reply as the model streams it. */
export interface ChatMessageDeltaFrame {
  type: 'message_delta';
  room_id: string;
  stream_id: string;
  delta: string;
}

/** The model abandoned a partial reply to call a tool — drop what was shown. */
export interface ChatMessageResetFrame {
  type: 'message_reset';
  room_id: string;
  stream_id: string;
}

/** End of a streamed reply; `content` is the full, now-persisted message. */
export interface ChatMessageDoneFrame {
  type: 'message_done';
  room_id: string;
  stream_id: string;
  sender_type?: ChatSenderType;
  sender_id?: string;
  content: string;
  attachment_url?: string | null;
  created_at?: string;
}

export type ChatServerFrame =
  | ChatHistoryFrame
  | ChatMessageFrame
  | ChatTypingFrame
  | ChatMessageDeltaFrame
  | ChatMessageResetFrame
  | ChatMessageDoneFrame;
