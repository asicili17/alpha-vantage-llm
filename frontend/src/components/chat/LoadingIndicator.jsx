import { Box, CircularProgress } from '@mui/material';

/**
 * Renders an animated loading indicator as an assistant message
 */
function LoadingIndicator() {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'flex-start', mb: 1 }}>
      <Box
        sx={{
          p: 2,
          bgcolor: 'grey.100',
          borderRadius: 1,
          display: 'flex',
          alignItems: 'center',
          gap: 1,
        }}
      >
        <CircularProgress size={20} />
      </Box>
    </Box>
  );
}

export default LoadingIndicator;
