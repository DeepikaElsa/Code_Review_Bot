import React from 'react';
import { ReviewProvider } from '../contexts/ReviewContext';
import Header from './Header';
import CodeEditor from './CodeEditor';
import ReviewOptions from './ReviewOptions';
import ReviewResult from './ReviewResult';
import HistorySidebar from './HistorySidebar';

const MainLayout: React.FC = () => {
  return (
    <ReviewProvider>
      <div className="flex h-screen bg-[#3D3C3A]">
        <aside className="w-80 border-r border-gray-700 overflow-y-auto bg-[#454545]">
          <HistorySidebar />
        </aside>
        <div className="flex-1 flex flex-col">
          <Header />
          <main className="flex-1 overflow-hidden flex">
            <div className="flex-1 flex flex-col p-6 overflow-hidden">
              <ReviewOptions />
              <div className="flex-1 overflow-y-auto space-y-6">
                <CodeEditor />
                <ReviewResult />
              </div>
            </div>
          </main>
        </div>
      </div>
    </ReviewProvider>
  );
};

export default MainLayout;