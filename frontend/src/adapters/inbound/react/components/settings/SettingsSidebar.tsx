export interface SidebarItem {
  id: string;
  label: string;
}

export interface SidebarGroup {
  id: string;
  label: string;
  /** Optional Heroicon outline path (24x24 viewBox, stroke-based). */
  iconPath?: string;
  items: SidebarItem[];
}

interface Props {
  groups: SidebarGroup[];
  activeItem: string;
  onSelect: (id: string) => void;
}

export function SettingsSidebar(props: Props) {
  return (
    <nav aria-label="Configuraciones" className="w-full">
      {props.groups.map((group) => (
        <div key={group.id} className="mb-6">
          <div className="mb-1 flex items-center gap-2 px-3">
            {group.iconPath !== undefined ? (
              <svg
                aria-hidden="true"
                className="h-3.5 w-3.5 text-slate-400"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                viewBox="0 0 24 24"
              >
                <path d={group.iconPath} strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            ) : null}
            <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              {group.label}
            </p>
          </div>
          <ul role="list">
            {group.items.map((item) => {
              const isActive = item.id === props.activeItem;
              return (
                <li key={item.id}>
                  <button
                    aria-current={isActive ? "page" : undefined}
                    className={[
                      "w-full rounded-lg px-3 py-2 text-left text-sm transition-colors",
                      isActive
                        ? "bg-brand-teal/10 font-semibold text-brand-teal"
                        : "font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                    ].join(" ")}
                    onClick={() => {
                      props.onSelect(item.id);
                    }}
                    type="button"
                  >
                    {item.label}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}
