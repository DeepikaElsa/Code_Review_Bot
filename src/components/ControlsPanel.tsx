import React from 'react';
import { SlidersHorizontal } from 'lucide-react';
import ReviewOptions from './ReviewOptions';
import Toolbar from './Toolbar';

/** Right-hand configuration column: modes, language, and model. */
const ControlsPanel: React.FC = () => {
  return (
    <div className="h-full flex flex-col bg-ink-900">
      <div className="flex items-center gap-2 px-4 h-14 border-b border-white/5 flex-none">
        <SlidersHorizontal size={16} className="text-sky" />
        <h2 className="text-sm font-semibold text-fg">Options</h2>
      </div>

      <div className="flex-1 overflow-y-auto scroll-slim p-4 space-y-6">
        <ReviewOptions />
        <div className="h-px bg-white/5" />
        <Toolbar />
      </div>
    </div>
  );
};

export default ControlsPanel;
