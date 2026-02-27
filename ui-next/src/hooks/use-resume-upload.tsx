"use client";

import { createContext, useContext, useCallback, useRef, useState, type ReactNode } from "react";
import { uploadResume } from "@/lib/api";

interface ResumeUploadState {
  /** True while the upload + LLM extraction is in progress */
  isUploading: boolean;
  /** Error message from the last upload attempt (null if none) */
  error: string | null;
  /** Extracted data from the last successful upload (null if none) */
  lastExtracted: { candidate: any; skills: any; experience: any } | null;
  /** Start an upload. Persists across page navigations. */
  startUpload: (file: File) => Promise<void>;
  /** Clear the last extracted data (after the settings page has consumed it) */
  clearExtracted: () => void;
}

const ResumeUploadContext = createContext<ResumeUploadState>({
  isUploading: false,
  error: null,
  lastExtracted: null,
  startUpload: async () => {},
  clearExtracted: () => {},
});

export function ResumeUploadProvider({ children }: { children: ReactNode }) {
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastExtracted, setLastExtracted] = useState<ResumeUploadState["lastExtracted"]>(null);
  // Guard against double uploads
  const uploadingRef = useRef(false);

  const startUpload = useCallback(async (file: File) => {
    if (uploadingRef.current) return;
    uploadingRef.current = true;
    setIsUploading(true);
    setError(null);
    setLastExtracted(null);

    try {
      const result = await uploadResume(file);
      setLastExtracted(result.extracted);
    } catch (e: any) {
      setError(e.message || "Upload failed");
    } finally {
      uploadingRef.current = false;
      setIsUploading(false);
    }
  }, []);

  const clearExtracted = useCallback(() => setLastExtracted(null), []);

  return (
    <ResumeUploadContext.Provider value={{ isUploading, error, lastExtracted, startUpload, clearExtracted }}>
      {children}
    </ResumeUploadContext.Provider>
  );
}

export function useResumeUpload() {
  return useContext(ResumeUploadContext);
}
