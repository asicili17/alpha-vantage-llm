import { useState } from 'react';
import { Box, TextField, IconButton } from '@mui/material';
import SendIcon from '@mui/icons-material/Send';

/**
 * Renders the message input form at the bottom of the chat
 * @param {Object} props
 * @param {Function} props.onSend - Callback function called with message text when sent
 * @param {boolean} props.disabled - Whether the input should be disabled
 */
function InputBar({ onSend, disabled }) {
  const [message, setMessage] = useState('');
  
  const handleSubmit = (e) => {
    e.preventDefault();
    if (message.trim() && !disabled) {
      onSend(message.trim());
      setMessage('');
    }
  };
  
  const handleKeyDown = (e) => {
    // Send on Enter, newline on Shift+Enter
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };
  
  return (
    <Box
      component="form"
      onSubmit={handleSubmit}
      sx={{
        p: 2,
        borderTop: 1,
        borderColor: 'divider',
        display: 'flex',
        gap: 1,
      }}
    >
      <TextField
        fullWidth
        multiline
        maxRows={4}
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask about earnings calls..."
        disabled={disabled}
        variant="outlined"
        size="small"
      />
      <IconButton
        type="submit"
        color="primary"
        disabled={!message.trim() || disabled}
        sx={{ alignSelf: 'flex-end' }}
      >
        <SendIcon />
      </IconButton>
    </Box>
  );
}

export default InputBar;
