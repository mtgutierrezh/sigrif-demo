import { Search } from "lucide-react";

interface SearchBoxProps {
  value: string;
  onChange: (value: string) => void;
  label?: string;
  placeholder?: string;
}

export function SearchBox({
  value,
  onChange,
  label = "Buscar zona",
  placeholder = "Buscar por zona o comuna",
}: SearchBoxProps) {
  return (
    <div className="relative">
      <Search
        size={16}
        strokeWidth={1.5}
        className="pointer-events-none absolute left-0 top-1/2 -translate-y-1/2 text-ash"
        aria-hidden="true"
      />
      <input
        type="search"
        className="input pl-7"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-label={label}
        placeholder={placeholder}
      />
    </div>
  );
}
