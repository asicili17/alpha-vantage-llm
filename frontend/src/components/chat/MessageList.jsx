/**
 * MessageList component - displays scrollable message history
 */

import { useEffect, useRef } from 'react';
import { Box, Typography, Stack } from '@mui/material';
import MessageBubble from './MessageBubble';
import LoadingIndicator from './LoadingIndicator';

/**
 * Renders the scrollable message list with auto-scroll to bottom
 * @param {Object} props
 * @param {Array} props.messages - Array of {role, content, citations} message objects
 * @param {boolean} props.loading - Whether the assistant is responding
 */
function MessageList({ messages, loading }) {
  const messagesEndRef = useRef(null);
  
  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);
  
  return (
    <Box
      sx={{
        height: '100%',
        overflowY: 'auto',
        p: 2,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {messages.length === 0 && !loading ? (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            gap: 1,
          }}
        >
          <Typography variant="body1" color="text.secondary">
            Start a conversation about earnings calls...
          </Typography>
          <Typography variant="body2" color="text.disabled">
            Try asking: "What were the key highlights from Apple's latest earnings?"
          </Typography>
        </Box>
      ) : (
        <Stack spacing={2}>
          {messages.map((message, index) => (
            <MessageBubble
              key={index}
              role={message.role}
              content={message.content}
              citations={message.citations}
            />
          ))}
          {loading && <LoadingIndicator />}
          <div ref={messagesEndRef} />
        </Stack>
      )}
    </Box>
  );
}

export default MessageList;
