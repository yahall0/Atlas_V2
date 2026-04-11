"use client";

interface Props {
  percentage: number;
  totalExpected: number;
  totalPresent: number;
  totalGaps: number;
}

export default function CoverageMeter({
  percentage, totalExpected, totalPresent, totalGaps,
}: Props) {
  const color =
    percentage >= 80 ? "text-green-600" :
    percentage >= 50 ? "text-yellow-600" :
    "text-red-600";

  const strokeColor =
    percentage >= 80 ? "stroke-green-500" :
    percentage >= 50 ? "stroke-yellow-500" :
    "stroke-red-500";

  const radius = 36;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percentage / 100) * circumference;

  return (
    <div className="flex items-center gap-4 p-3 rounded-lg border bg-slate-50">
      {/* Circular progress */}
      <div className="relative w-20 h-20 shrink-0">
        <svg className="w-20 h-20 -rotate-90" viewBox="0 0 80 80">
          <circle
            cx="40" cy="40" r={radius}
            className="stroke-gray-200"
            fill="none" strokeWidth="6"
          />
          <circle
            cx="40" cy="40" r={radius}
            className={strokeColor}
            fill="none" strokeWidth="6"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
          />
        </svg>
        <div className={`absolute inset-0 flex items-center justify-center text-lg font-bold ${color}`}>
          {Math.round(percentage)}%
        </div>
      </div>

      {/* Stats */}
      <div className="text-sm space-y-0.5">
        <p className="font-semibold">Evidence Coverage</p>
        <p className="text-muted-foreground">
          {totalPresent} of {totalExpected} expected present
        </p>
        <p className={`font-medium ${totalGaps > 0 ? "text-red-600" : "text-green-600"}`}>
          {totalGaps} gap{totalGaps !== 1 ? "s" : ""} found
        </p>
      </div>
    </div>
  );
}
