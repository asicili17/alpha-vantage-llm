/**
 * MessageBubble component - displays a single chat message
 */

import { Box, Paper, Typography } from '@mui/material';
import Citations from '../common/Citations';

/**
 * Renders a single message bubble with optional citations
 * @param {Object} props
 * @param {string} props.role - 'user' or 'assistant'
 * @param {string} props.content - Message text content
 * @param {Array} props.citations - Optional array of citations (for assistant messages)
 */
function MessageBubble({ role, content, citations }) {
  const isUser = role === 'user';
  
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        mb: 1,
      }}
    >
      <Paper
        elevation={1}
        sx={{
          maxWidth: '70%',
          p: 2,
          bgcolor: isUser ? 'primary.main' : 'grey.100',
          color: isUser ? 'primary.contrastText' : 'text.primary',
        }}
      >
        <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {content}
        </Typography>
        {citations && citations.length > 0 && <Citations citations={citations} />}
      </Paper>
    </Box>
  );
}

export default MessageBubble;
