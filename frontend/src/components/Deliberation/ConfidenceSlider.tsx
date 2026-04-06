import { useState } from 'react';
import { motion } from 'framer-motion';

interface ConfidenceSliderProps {
  onSubmit: (scores: Record<string, number>) => void;
  onCancel: () => void;
}

const ASPECTS = [
  { key: 'tech_stack', label: 'Tech stack choice' },
  { key: 'market', label: 'Target market exists' },
  { key: 'timeline', label: 'Timeline feasibility' },
];

export function ConfidenceSlider({ onSubmit, onCancel }: ConfidenceSliderProps) {
  const [scores, setScores] = useState<Record<string, number>>(
    Object.fromEntries(ASPECTS.map((a) => [a.key, 5])),
  );

  const labels = ['Not confident', '', '', '', 'Moderate', '', '', '', '', 'Very confident'];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="border-t border-friction-border bg-friction-darker p-4"
    >
      <h4 className="text-sm font-semibold text-friction-amber mb-3">
        Rate your confidence before Friction shares its analysis
      </h4>

      <div className="space-y-4">
        {ASPECTS.map((aspect) => (
          <div key={aspect.key}>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-gray-300">{aspect.label}</span>
              <span className="text-friction-amber font-medium">{scores[aspect.key]}/10</span>
            </div>
            <input
              type="range"
              min={1}
              max={10}
              value={scores[aspect.key]}
              onChange={(e) =>
                setScores((s) => ({ ...s, [aspect.key]: Number(e.target.value) }))
              }
              className="w-full h-1.5 bg-friction-border rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-friction-amber [&::-webkit-slider-thumb]:cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-friction-muted mt-0.5">
              <span>{labels[0]}</span>
              <span>{labels[4]}</span>
              <span>{labels[9]}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="flex gap-2 mt-4">
        <button
          onClick={() => onSubmit(scores)}
          className="flex-1 py-2 text-sm font-medium rounded-lg bg-friction-amber text-black hover:bg-friction-amber/90"
        >
          Submit Ratings
        </button>
        <button
          onClick={onCancel}
          className="px-4 py-2 text-sm rounded-lg text-gray-400 hover:text-gray-200 hover:bg-friction-surface"
        >
          Cancel
        </button>
      </div>
    </motion.div>
  );
}
