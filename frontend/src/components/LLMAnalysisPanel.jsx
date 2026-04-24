import { Brain } from 'lucide-react';

function getFinalAnalysis(analyses) {
  if (!analyses?.length) return null;

  const finalSummary = analyses.find((a) => a.file_path === 'FINAL_SUMMARY');
  if (finalSummary) return finalSummary;

  if (analyses.length === 1) return analyses[0];

  return {
    file_path: 'FINAL_SUMMARY',
    summary: analyses.map((a) => a.summary).filter(Boolean).join('\n\n'),
    quality_assessment: analyses.map((a) => a.quality_assessment).filter(Boolean).join('\n'),
    interview_notes: analyses.map((a) => a.interview_notes).filter(Boolean).join('\n\n'),
  };
}

function extractCreativeSections(interviewNotes = '') {
  if (!interviewNotes) {
    return { creativity: '', differentApproach: '' };
  }

  const creativityMatch = interviewNotes.match(
    /CREATIVITY:\s*([\s\S]*?)(?:\n\s*DIFFERENT APPROACH:\s*|$)/i,
  );
  const differentApproachMatch = interviewNotes.match(
    /DIFFERENT APPROACH:\s*([\s\S]*)$/i,
  );

  const creativity = creativityMatch?.[1]?.trim() || '';
  const differentApproach = differentApproachMatch?.[1]?.trim() || '';

  if (!creativity && !differentApproach) {
    return { creativity: interviewNotes.trim(), differentApproach: '' };
  }

  return { creativity, differentApproach };
}

export default function LLMAnalysisPanel({ analyses }) {
  const finalAnalysis = getFinalAnalysis(analyses);

  if (!finalAnalysis) {
    return (
      <div className="card fade-in" id="llm-panel">
        <div className="card-header">
          <h3 className="card-title">
            <Brain size={20} />
            Final AI Summary
          </h3>
        </div>
        <div className="empty-state" style={{ padding: 'var(--space-xl)' }}>
          <div className="empty-state-icon" style={{ width: 56, height: 56 }}>
            <Brain size={24} />
          </div>
          <h3 style={{ fontSize: 'var(--text-base)' }}>No AI summary</h3>
          <p style={{ fontSize: 'var(--text-sm)' }}>LLM analysis was not run or produced no summary.</p>
        </div>
      </div>
    );
  }

  const { creativity, differentApproach } = extractCreativeSections(finalAnalysis.interview_notes || '');

  return (
    <div className="card fade-in" id="llm-panel">
      <div className="card-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h3 className="card-title">
          <Brain size={20} />
          Final AI Summary
        </h3>
        <span className="badge badge-neutral">1 final summary</span>
      </div>

      {finalAnalysis.summary && (
        <div className="analysis-section">
          <h4>Code Greatness & Functionality</h4>
          <p>{finalAnalysis.summary}</p>
        </div>
      )}

      {finalAnalysis.quality_assessment && (
        <div className="analysis-section">
          <h4>Key Points</h4>
          <p style={{ whiteSpace: 'pre-wrap' }}>{finalAnalysis.quality_assessment}</p>
        </div>
      )}

      {creativity && (
        <div className="analysis-section">
          <h4>Creativity</h4>
          <p style={{ whiteSpace: 'pre-wrap' }}>{creativity}</p>
        </div>
      )}

      {differentApproach && (
        <div className="analysis-section">
          <h4>Different Approach</h4>
          <p style={{ whiteSpace: 'pre-wrap' }}>{differentApproach}</p>
        </div>
      )}
    </div>
  );
}
