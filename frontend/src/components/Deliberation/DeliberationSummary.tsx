import { motion } from 'framer-motion';
import { Lightbulb, AlertTriangle, ArrowRight } from 'lucide-react';
import { useFrictionStore } from '@/store/useFrictionStore';

export function DeliberationSummary() {
  const { activeSession, tickets, completeDeliberation, isGeneratingTickets } = useFrictionStore();

  if (!activeSession || activeSession.status !== 'completed') return null;

  const hasTickets = tickets.length > 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="border-t border-friction-amber/20 bg-friction-amber/5 p-4 space-y-3 shrink-0"
    >
      <h3 className="text-sm font-semibold text-friction-amber flex items-center gap-2">
        <Lightbulb className="w-4 h-4" />
        Deliberation Complete
      </h3>

      {activeSession.refined_idea && (
        <p className="text-sm text-gray-300">{activeSession.refined_idea}</p>
      )}

      {activeSession.key_insights.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Key Insights</h4>
          <ul className="space-y-1">
            {activeSession.key_insights.map((insight, i) => (
              <li key={i} className="text-xs text-gray-300 flex items-start gap-1.5">
                <ArrowRight className="w-3 h-3 text-friction-amber mt-0.5 shrink-0" />
                {insight}
              </li>
            ))}
          </ul>
        </div>
      )}

      {activeSession.risks.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Risks</h4>
          <ul className="space-y-1">
            {activeSession.risks.map((risk, i) => (
              <li key={i} className="text-xs text-gray-300 flex items-start gap-1.5">
                <AlertTriangle className="w-3 h-3 text-friction-red mt-0.5 shrink-0" />
                {risk}
              </li>
            ))}
          </ul>
        </div>
      )}

      {!hasTickets && (
        <button
          onClick={completeDeliberation}
          disabled={isGeneratingTickets}
          className="w-full py-2.5 rounded-lg bg-friction-amber text-black font-semibold text-sm hover:bg-friction-amber/90 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
        >
          {isGeneratingTickets ? 'Generating...' : 'View Tickets'}
        </button>
      )}
    </motion.div>
  );
}
