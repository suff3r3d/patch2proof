"use client";

import { useState, useEffect, useCallback } from "react";

const STORAGE_KEY = "p2p_active_case_id";
const EVENT_NAME = "p2p-active-case-change";
const DEFAULT_CASE_ID = "CVE-2024-27287";

export function getStoredActiveCaseId(): string {
  if (typeof window === "undefined") return DEFAULT_CASE_ID;
  return window.localStorage.getItem(STORAGE_KEY) || DEFAULT_CASE_ID;
}

export function setStoredActiveCaseId(caseId: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, caseId);
  window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: { caseId } }));
}

export function useActiveCaseId(): [string, (id: string) => void] {
  const [activeCaseId, setActiveCaseIdState] = useState<string>(DEFAULT_CASE_ID);

  useEffect(() => {
    setActiveCaseIdState(getStoredActiveCaseId());

    const handler = (e: Event) => {
      const custom = e as CustomEvent<{ caseId: string }>;
      if (custom.detail?.caseId) {
        setActiveCaseIdState(custom.detail.caseId);
      } else {
        setActiveCaseIdState(getStoredActiveCaseId());
      }
    };

    window.addEventListener(EVENT_NAME, handler);
    window.addEventListener("storage", handler);
    return () => {
      window.removeEventListener(EVENT_NAME, handler);
      window.removeEventListener("storage", handler);
    };
  }, []);

  const updateActiveCaseId = useCallback((id: string) => {
    setActiveCaseIdState(id);
    setStoredActiveCaseId(id);
  }, []);

  return [activeCaseId, updateActiveCaseId];
}
