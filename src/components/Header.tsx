import React from 'react';
import { Code } from 'lucide-react';

const Header: React.FC = () => {
  return (
    <header className="bg-[#3D3C3A] border-b border-gray-700 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center">
          <Code size={24} className="text-[#1ABC9C] mr-2" />
          <h1 className="text-xl font-semibold text-gray-200">CodeReviewBot</h1>
        </div>
        <div>
          <button className="text-sm text-gray-300 hover:text-gray-100 transition-colors">
            Help
          </button>
        </div>
      </div>
    </header>
  );
};

export default Header;