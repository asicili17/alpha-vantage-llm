import { Accordion, AccordionSummary, AccordionDetails, Typography, Chip, Box } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

/**
 * Renders an expandable citations list with chunk references
 * @param {Object} props
 * @param {Array} props.citations - Array of {chunk_id, short_quote} objects
 */
function Citations({ citations }) {
  if (!citations || citations.length === 0) {
    return null;
  }

  return (
    <Accordion
      sx={{
        mt: 1,
        bgcolor: 'rgba(0, 0, 0, 0.05)',
        boxShadow: 'none',
        '&:before': { display: 'none' },
      }}
    >
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Typography variant="caption" sx={{ fontWeight: 500 }}>
          {citations.length} {citations.length === 1 ? 'source' : 'sources'}
        </Typography>
      </AccordionSummary>
      <AccordionDetails>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {citations.map((citation, index) => (
            <Box key={index} sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
              <Chip
                label={citation.chunk_id.slice(-6)}
                size="small"
                variant="outlined"
              />
              <Typography variant="body2" sx={{ flex: 1, fontStyle: 'italic' }}>
                "{citation.short_quote}"
              </Typography>
            </Box>
          ))}
        </Box>
      </AccordionDetails>
    </Accordion>
  );
}

export default Citations;
