import * as reactModule from "react";

const STORAGE_KEY = "sidebar-collapsed";

function readFromStorage(): boolean {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === null) {
      return false;
    }
    return stored === "true";
  } catch {
    return false;
  }
}

function writeToStorage(value: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, String(value));
  } catch {
    // ignore
  }
}

export function useSidebarCollapsed(): [boolean, () => void] {
  const [isCollapsed, setIsCollapsed] = reactModule.useState<boolean>(readFromStorage);

  const toggle = reactModule.useCallback(() => {
    setIsCollapsed((current) => {
      const next = !current;
      writeToStorage(next);
      return next;
    });
  }, []);

  return [isCollapsed, toggle];
}
