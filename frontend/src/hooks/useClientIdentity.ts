import { useState, useEffect } from 'react';

const STORAGE_KEY = 'marketmind_client_id';

function generateUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function useClientIdentity() {
  const [clientId, setClientId] = useState<string>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) return stored;
      const fresh = generateUUID();
      localStorage.setItem(STORAGE_KEY, fresh);
      return fresh;
    } catch {
      return generateUUID();
    }
  });

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (!stored) {
        localStorage.setItem(STORAGE_KEY, clientId);
      }
    } catch (e) {
      console.warn('LocalStorage access error:', e);
    }
  }, [clientId]);

  const resetIdentity = () => {
    const fresh = generateUUID();
    try {
      localStorage.setItem(STORAGE_KEY, fresh);
    } catch (e) {
      console.warn('LocalStorage error:', e);
    }
    setClientId(fresh);
    return fresh;
  };

  return { clientId, resetIdentity };
}
