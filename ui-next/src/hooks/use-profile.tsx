"use client";

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";

interface ProfileContextValue {
  profileId: number;
  setProfileId: (id: number) => void;
}

const ProfileContext = createContext<ProfileContextValue>({
  profileId: 1,
  setProfileId: () => {},
});

const STORAGE_KEY = "job-tracker-profile-id";

export function ProfileProvider({ children }: { children: ReactNode }) {
  const [profileId, setProfileIdState] = useState<number>(1);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = parseInt(stored, 10);
      if (!isNaN(parsed) && parsed > 0) {
        setProfileIdState(parsed);
      }
    }
  }, []);

  const setProfileId = useCallback((id: number) => {
    setProfileIdState(id);
    localStorage.setItem(STORAGE_KEY, String(id));
  }, []);

  return (
    <ProfileContext.Provider value={{ profileId, setProfileId }}>
      {children}
    </ProfileContext.Provider>
  );
}

export function useProfile() {
  return useContext(ProfileContext);
}

export function isDemoMode(): boolean {
  return process.env.NEXT_PUBLIC_DEMO_MODE === "true";
}
