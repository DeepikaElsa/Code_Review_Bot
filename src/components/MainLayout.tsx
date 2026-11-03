import React from 'react';
import { ReviewProvider } from '../contexts/ReviewContext';
import Header from './Header';
import HistorySidebar from './HistorySidebar';
import Transcript from './Transcript';
import Composer from './Composer';
import ControlsPanel from './ControlsPanel';

const MainLayout: React.FC = () => {
  return (
    <ReviewProvider>
      <div className="flex flex-col h-screen bg-ink-950 text-fg">
        <Header />

        <div className="flex flex-1 overflow-hidden">
          {/* Left: history */}
          <aside className="w-72 flex-none border-r border-white/5 hidden md:block">
            <HistorySidebar />
          </aside>

          {/* Center: chat transcript + composer */}
          <section className="flex-1 flex flex-col min-w-0">
            <Transcript />
            <Composer />
          </section>

          {/* Right: controls */}
          <aside className="w-80 flex-none border-l border-white/5 hidden lg:block">
            <ControlsPanel />
          </aside>
        </div>
      </div>
    </ReviewProvider>
  );
};

export default MainLayout;
