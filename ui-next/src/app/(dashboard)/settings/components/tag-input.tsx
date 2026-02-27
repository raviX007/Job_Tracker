"use client";

import { useState, useRef, type KeyboardEvent } from "react";
import { X } from "lucide-react";

interface TagInputProps {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
}

export function TagInput({ value, onChange, placeholder = "Type and press Enter" }: TagInputProps) {
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  function addTag(tag: string) {
    const trimmed = tag.trim();
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed]);
    }
    setInput("");
  }

  function removeTag(index: number) {
    onChange(value.filter((_, i) => i !== index));
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTag(input);
    } else if (e.key === "Backspace" && !input && value.length > 0) {
      removeTag(value.length - 1);
    }
  }

  function handlePaste(e: React.ClipboardEvent<HTMLInputElement>) {
    const text = e.clipboardData.getData("text");
    if (text.includes(",")) {
      e.preventDefault();
      const tags = text.split(",").map((t) => t.trim()).filter(Boolean);
      const unique = tags.filter((t) => !value.includes(t));
      if (unique.length > 0) {
        onChange([...value, ...unique]);
      }
    }
  }

  return (
    <div
      className="flex min-h-[40px] flex-wrap items-center gap-1.5 rounded-md border border-input bg-background px-2 py-1.5 focus-within:ring-2 focus-within:ring-ring"
      onClick={() => inputRef.current?.focus()}
    >
      {value.map((tag, i) => (
        <span
          key={`${tag}-${i}`}
          className="inline-flex items-center gap-1 rounded-md bg-accent/15 px-2 py-0.5 text-xs font-medium text-accent-foreground"
        >
          {tag}
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); removeTag(i); }}
            className="rounded-full p-0.5 hover:bg-accent/30"
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
      <input
        ref={inputRef}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        onBlur={() => { if (input.trim()) addTag(input); }}
        placeholder={value.length === 0 ? placeholder : ""}
        className="min-w-[100px] flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
      />
    </div>
  );
}
