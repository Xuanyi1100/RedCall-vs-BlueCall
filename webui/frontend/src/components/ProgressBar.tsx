interface ProgressBarProps {
  value: number; // 0 to 1
  color: 'red' | 'blue' | 'yellow' | 'green';
}

const colorClasses = {
  red: 'bg-gradient-to-r from-red-600 to-red-400',
  blue: 'bg-gradient-to-r from-blue-600 to-blue-400',
  yellow: 'bg-gradient-to-r from-yellow-600 to-yellow-400',
  green: 'bg-gradient-to-r from-green-600 to-green-400',
};

export function ProgressBar({ value, color }: ProgressBarProps) {
  const percentage = Math.max(0, Math.min(100, value * 100));
  
  return (
    <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full transition-all duration-500 ease-out ${colorClasses[color]}`}
        style={{ width: `${percentage}%` }}
      />
    </div>
  );
}
