"use client";

import { useEffect, useRef } from "react";
import { Upload, FileText, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useResumeUpload } from "@/hooks/use-resume-upload";

const ALLOWED_EXTENSIONS = [".pdf", ".tex"];

interface ResumeUploadProps {
  onExtracted: (data: { candidate: any; skills: any; experience: any }) => void;
  currentFilename?: string | null;
  disabled?: boolean;
}

export function ResumeUpload({ onExtracted, currentFilename, disabled }: ResumeUploadProps) {
  const { isUploading, error, lastExtracted, startUpload, clearExtracted } = useResumeUpload();
  const fileRef = useRef<HTMLInputElement>(null);
  const consumedRef = useRef(false);

  // When extraction completes (even after navigating away and back), deliver the result
  useEffect(() => {
    if (lastExtracted && !consumedRef.current) {
      consumedRef.current = true;
      try {
        onExtracted(lastExtracted);
      } catch (err) {
        console.error("Failed to apply extracted resume data:", err);
      }
      clearExtracted();
    }
  }, [lastExtracted, onExtracted, clearExtracted]);

  // Reset consumed flag when a new upload starts
  useEffect(() => {
    if (isUploading) consumedRef.current = false;
  }, [isUploading]);

  function validateAndUpload(file: File) {
    if (isUploading || disabled) return;

    const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      return;
    }

    startUpload(file);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    if (isUploading || disabled) return;
    const file = e.dataTransfer.files[0];
    if (file) validateAndUpload(file);
  }

  const isDisabled = isUploading || disabled;

  return (
    <div className="space-y-3">
      <div
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        className={`flex flex-col items-center gap-3 rounded-lg border-2 border-dashed p-6 text-center transition-colors ${
          isDisabled
            ? "pointer-events-none border-muted-foreground/20 opacity-60"
            : "border-muted-foreground/30 hover:border-accent/50"
        }`}
      >
        {isUploading ? (
          <>
            <Loader2 className="h-8 w-8 animate-spin text-accent" />
            <p className="text-sm text-muted-foreground">Extracting profile from resume...</p>
          </>
        ) : (
          <>
            <Upload className="h-8 w-8 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium">Drop your resume here (PDF or LaTeX)</p>
              <p className="text-xs text-muted-foreground">or click to browse (max 5 MB)</p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => fileRef.current?.click()}
              disabled={isDisabled}
            >
              Choose File
            </Button>
          </>
        )}
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.tex"
          className="hidden"
          disabled={isDisabled}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) validateAndUpload(file);
            if (e.target) e.target.value = "";
          }}
        />
      </div>

      {currentFilename && !isUploading && (
        <div className="flex items-center gap-2 rounded-md bg-accent/10 px-3 py-2 text-sm">
          <FileText className="h-4 w-4 text-accent" />
          <span className="text-muted-foreground">Uploaded:</span>
          <span className="font-medium">{currentFilename}</span>
        </div>
      )}

      {error && (
        <p className="text-sm text-red-500">{error}</p>
      )}
    </div>
  );
}
