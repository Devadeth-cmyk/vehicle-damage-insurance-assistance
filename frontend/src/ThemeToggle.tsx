import React from 'react';
import { Moon, Sun } from 'lucide-react';

interface ThemeToggleProps {
  theme: 'light' | 'dark';
  onToggle: () => void;
  floating?: boolean;
}

export const ThemeToggle: React.FC<ThemeToggleProps> = ({ theme, onToggle, floating = false }) => (
  <button
    className={`theme-toggle${floating ? ' theme-toggle--floating' : ''}`}
    type="button"
    onClick={onToggle}
    aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
    title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
  >
    {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
    <span>{theme === 'light' ? 'Dark mode' : 'Light mode'}</span>
  </button>
);
