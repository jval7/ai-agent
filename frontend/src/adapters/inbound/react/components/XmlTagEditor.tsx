import * as reactModule from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ParsedSection {
  id: string;
  kind: "text" | "tag";
  tagName: string | null;
  content: string;
}

interface ParseResult {
  wrapperTagName: string | null;
  sections: ParsedSection[];
}

interface XmlTagEditorProps {
  value: string;
  onChange: (nextValue: string) => void;
  disabled?: boolean;
}

// ---------------------------------------------------------------------------
// Parser: text <-> sections  (supports nested tags)
// ---------------------------------------------------------------------------

const OPEN_TAG_REGEX = /<(\w+)>/g;

let nextSectionId = 0;
function createSectionId(): string {
  nextSectionId += 1;
  return `section-${nextSectionId}`;
}

/**
 * Pretty-prints XML-like content with consistent indentation.
 * Tags at the same depth are aligned; text inside tags is indented one level deeper.
 */
function formatXmlContent(raw: string): string {
  const lines = raw.split("\n");
  const result: string[] = [];
  let depth = 0;
  const indent = "  ";

  for (const rawLine of lines) {
    const stripped = rawLine.trim();
    if (stripped === "") {
      result.push("");
      continue;
    }

    // Closing tag at start of line → decrease depth before printing
    if (/^<\/\w+>/.test(stripped)) {
      depth = Math.max(0, depth - 1);
    }

    result.push(indent.repeat(depth) + stripped);

    // Opening tag that does NOT close on the same line → increase depth
    if (/^<\w+>/.test(stripped) && !stripped.startsWith("</") && !/<\/\w+>\s*$/.test(stripped)) {
      depth += 1;
    }
  }

  return result.join("\n");
}

/**
 * Finds top-level XML tags by tracking nesting depth.
 * Nested tags inside a top-level tag are kept as-is in the content.
 */
function parseXmlSections(raw: string): ParsedSection[] {
  const sections: ParsedSection[] = [];
  let cursor = 0;

  while (cursor < raw.length) {
    // Find the next opening tag from current cursor
    OPEN_TAG_REGEX.lastIndex = cursor;
    const openMatch = OPEN_TAG_REGEX.exec(raw);

    if (openMatch?.index === undefined) {
      // No more tags — rest is trailing text
      const trailing = raw.slice(cursor);
      if (trailing.trim() !== "") {
        sections.push({
          id: createSectionId(),
          kind: "text",
          tagName: null,
          content: formatXmlContent(trailing.trim())
        });
      }
      break;
    }

    const tagName = openMatch[1] ?? "section";
    const tagOpenStart = openMatch.index;

    // Text before this tag
    if (tagOpenStart > cursor) {
      const textBefore = raw.slice(cursor, tagOpenStart);
      if (textBefore.trim() !== "") {
        sections.push({
          id: createSectionId(),
          kind: "text",
          tagName: null,
          content: formatXmlContent(textBefore.trim())
        });
      }
    }

    // Walk forward tracking depth to find the matching close tag
    const contentStart = tagOpenStart + openMatch[0].length;
    const closeTag = `</${tagName}>`;
    const openTag = `<${tagName}>`;
    let depth = 1;
    let searchPos = contentStart;
    let closeEnd = -1;
    let contentEnd = -1;

    while (depth > 0 && searchPos < raw.length) {
      const nextOpen = raw.indexOf(openTag, searchPos);
      const nextClose = raw.indexOf(closeTag, searchPos);

      if (nextClose === -1) {
        // No matching close tag found — treat as plain text
        break;
      }

      if (nextOpen !== -1 && nextOpen < nextClose) {
        // Found a nested open tag before the next close
        depth += 1;
        searchPos = nextOpen + openTag.length;
      } else {
        // Found a close tag
        depth -= 1;
        if (depth === 0) {
          contentEnd = nextClose;
          closeEnd = nextClose + closeTag.length;
        } else {
          searchPos = nextClose + closeTag.length;
        }
      }
    }

    if (contentEnd === -1 || closeEnd === -1) {
      // Unmatched tag — treat from tag start to end as text
      const rest = raw.slice(tagOpenStart);
      if (rest.trim() !== "") {
        sections.push({
          id: createSectionId(),
          kind: "text",
          tagName: null,
          content: formatXmlContent(rest.trim())
        });
      }
      break;
    }

    sections.push({
      id: createSectionId(),
      kind: "tag",
      tagName,
      content: formatXmlContent(raw.slice(contentStart, contentEnd).trim())
    });

    cursor = closeEnd;
  }

  // If nothing was parsed, treat entire content as one text section
  if (sections.length === 0 && raw.trim() !== "") {
    sections.push({
      id: createSectionId(),
      kind: "text",
      tagName: null,
      content: formatXmlContent(raw.trim())
    });
  }

  return sections;
}

/**
 * Top-level parse: if the entire content is wrapped in a single tag,
 * unwrap it and parse the children as the collapsible sections.
 */
function parseXmlDocument(raw: string): ParseResult {
  const topLevel = parseXmlSections(raw);

  // If there is exactly one top-level tag and no text sections,
  // unwrap it and parse its children as the navigable sections.
  if (topLevel.length === 1 && topLevel[0]?.kind === "tag") {
    const wrapper = topLevel[0];
    const children = parseXmlSections(wrapper.content);
    // Only unwrap if the children contain at least 2 tag sections
    const tagChildCount = children.filter((c) => c.kind === "tag").length;
    if (tagChildCount >= 2) {
      return { wrapperTagName: wrapper.tagName, sections: children };
    }
  }

  return { wrapperTagName: null, sections: topLevel };
}

function serializeSections(sections: ParsedSection[], wrapperTagName: string | null): string {
  const inner = sections
    .map((section) => {
      if (section.kind === "text") {
        return section.content;
      }
      return `<${section.tagName}>\n${section.content}\n</${section.tagName}>`;
    })
    .join("\n");

  if (wrapperTagName !== null) {
    return `<${wrapperTagName}>\n${inner}\n</${wrapperTagName}>`;
  }
  return inner;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function XmlTagEditor(props: XmlTagEditorProps) {
  const { value, onChange, disabled = false } = props;

  const [parseResult, setParseResult] = reactModule.useState<ParseResult>(() =>
    parseXmlDocument(value)
  );
  const sections = parseResult.sections;
  const wrapperTagName = parseResult.wrapperTagName;

  const setSections = (nextSections: ParsedSection[]) => {
    setParseResult((prev) => ({ ...prev, sections: nextSections }));
  };

  const [expandedIds, setExpandedIds] = reactModule.useState<Set<string>>(() => new Set());
  const [isRawView, setIsRawView] = reactModule.useState(false);
  const [editingTagNameId, setEditingTagNameId] = reactModule.useState<string | null>(null);
  const [editingTagNameValue, setEditingTagNameValue] = reactModule.useState("");

  // Sync sections when external value changes (e.g. API load)
  const lastExternalValue = reactModule.useRef(value);
  reactModule.useEffect(() => {
    if (value !== lastExternalValue.current) {
      lastExternalValue.current = value;
      setParseResult(parseXmlDocument(value));
    }
  }, [value]);

  // Propagate changes upward
  const propagate = reactModule.useCallback(
    (nextSections: ParsedSection[]) => {
      setSections(nextSections);
      const serialized = serializeSections(nextSections, wrapperTagName);
      lastExternalValue.current = serialized;
      onChange(serialized);
    },
    [onChange, wrapperTagName]
  );

  // Handlers
  const toggleSection = (sectionId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(sectionId)) {
        next.delete(sectionId);
      } else {
        next.add(sectionId);
      }
      return next;
    });
  };

  const expandAll = () => {
    setExpandedIds(new Set(sections.map((s) => s.id)));
  };

  const collapseAll = () => {
    setExpandedIds(new Set());
  };

  const updateSectionContent = (sectionId: string, content: string) => {
    const nextSections = sections.map((s) => (s.id === sectionId ? { ...s, content } : s));
    propagate(nextSections);
  };

  const removeSection = (sectionId: string) => {
    const nextSections = sections.filter((s) => s.id !== sectionId);
    propagate(nextSections);
  };

  const addSection = () => {
    const newSection: ParsedSection = {
      id: createSectionId(),
      kind: "tag",
      tagName: "nueva_seccion",
      content: ""
    };
    const nextSections = [...sections, newSection];
    propagate(nextSections);
    setExpandedIds((prev) => new Set([...prev, newSection.id]));
  };

  const startEditingTagName = (section: ParsedSection) => {
    setEditingTagNameId(section.id);
    setEditingTagNameValue(section.tagName ?? "");
  };

  const commitTagNameEdit = () => {
    if (editingTagNameId === null) {
      return;
    }
    const sanitized = editingTagNameValue.replace(/[^a-zA-Z0-9_]/g, "").trim();
    if (sanitized !== "") {
      const nextSections = sections.map((s) =>
        s.id === editingTagNameId ? { ...s, tagName: sanitized } : s
      );
      propagate(nextSections);
    }
    setEditingTagNameId(null);
    setEditingTagNameValue("");
  };

  const hasTags = sections.some((s) => s.kind === "tag");

  // ---- Raw view ----
  if (isRawView) {
    return (
      <div>
        <div className="mb-4 flex items-center justify-end gap-3">
          <span className="text-sm font-medium text-slate-600">Vista raw</span>
          <button
            className={[
              "relative h-6 w-11 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-brand-teal focus:ring-offset-2",
              "bg-brand-teal"
            ].join(" ")}
            onClick={() => {
              setIsRawView(false);
              setParseResult(parseXmlDocument(value));
            }}
            type="button"
          >
            <div className="absolute left-[1.375rem] top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform" />
          </button>
        </div>
        <textarea
          className="min-h-[400px] w-full rounded-lg border border-border-subtle px-3 py-2 font-mono text-sm leading-6 transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
          disabled={disabled}
          onChange={(e) => {
            onChange(e.target.value);
          }}
          value={value}
        />
      </div>
    );
  }

  // ---- Structured view ----
  return (
    <div>
      {/* Toolbar */}
      <div className="mb-4 flex flex-wrap items-center gap-3 border-b border-border-subtle pb-4">
        {hasTags ? (
          <>
            <button
              className="flex items-center gap-1.5 rounded-lg border border-border-subtle bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-100"
              onClick={collapseAll}
              type="button"
            >
              <ChevronUpIcon />
              Colapsar todo
            </button>
            <button
              className="flex items-center gap-1.5 rounded-lg border border-border-subtle bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-100"
              onClick={expandAll}
              type="button"
            >
              <ChevronDownIcon />
              Expandir todo
            </button>
            <div className="mx-1 h-5 w-px bg-slate-300" />
          </>
        ) : null}
        <button
          className="flex items-center gap-1.5 rounded-lg bg-brand-teal/10 px-3 py-1.5 text-xs font-medium text-brand-teal transition-colors hover:bg-brand-teal/20"
          disabled={disabled}
          onClick={addSection}
          type="button"
        >
          <PlusIcon />
          Agregar seccion
        </button>
        <div className="ml-auto flex items-center gap-3">
          <span className="text-sm font-medium text-slate-600">Vista raw</span>
          <button
            className={[
              "relative h-6 w-11 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-brand-teal focus:ring-offset-2",
              "bg-slate-200"
            ].join(" ")}
            onClick={() => {
              setIsRawView(true);
            }}
            type="button"
          >
            <div className="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform" />
          </button>
        </div>
      </div>

      {/* Wrapper indicator */}
      {wrapperTagName !== null ? (
        <div className="mb-3 flex items-center gap-2 text-xs text-slate-400">
          <span className="font-mono">&lt;{wrapperTagName}&gt;</span>
          <div className="h-px flex-1 bg-slate-200" />
        </div>
      ) : null}

      {/* Sections */}
      <div className="space-y-3">
        {sections.map((section) => {
          if (section.kind === "text") {
            return (
              <div key={section.id}>
                <label className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-700">
                  <TextIcon />
                  Texto base (sin etiquetas)
                </label>
                <textarea
                  className="min-h-[80px] w-full rounded-lg border border-border-subtle bg-slate-50 px-3 py-2 font-mono text-sm leading-relaxed text-slate-700 transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                  disabled={disabled}
                  onChange={(e) => {
                    updateSectionContent(section.id, e.target.value);
                  }}
                  value={section.content}
                />
              </div>
            );
          }

          const isExpanded = expandedIds.has(section.id);
          const isEditingName = editingTagNameId === section.id;

          return (
            <div
              className="relative overflow-hidden rounded-lg border border-border-subtle bg-white shadow-sm"
              key={section.id}
            >
              {/* Teal left accent */}
              <div
                className={[
                  "absolute bottom-0 left-0 top-0 w-1",
                  isExpanded ? "bg-brand-teal" : "bg-slate-300"
                ].join(" ")}
              />

              {/* Header */}
              <div
                className="flex cursor-pointer items-center justify-between bg-slate-50 p-3 pl-4 transition-colors hover:bg-slate-100"
                onClick={() => {
                  if (!isEditingName) {
                    toggleSection(section.id);
                  }
                }}
              >
                <div className="flex items-center gap-3">
                  {/* Tag name badge */}
                  {isEditingName ? (
                    <input
                      autoFocus
                      className="rounded border border-brand-teal bg-white px-2 py-0.5 font-mono text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-brand-teal/30"
                      onBlur={commitTagNameEdit}
                      onChange={(e) => {
                        setEditingTagNameValue(e.target.value);
                      }}
                      onClick={(e) => {
                        e.stopPropagation();
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          commitTagNameEdit();
                        }
                      }}
                      value={editingTagNameValue}
                    />
                  ) : (
                    <span className="flex items-center gap-0.5 rounded border border-border-subtle bg-white px-2.5 py-0.5 font-mono text-xs text-slate-600 shadow-sm">
                      <span className="font-bold text-brand-teal">&lt;</span>
                      {section.tagName}
                      <span className="font-bold text-brand-teal">&gt;</span>
                    </span>
                  )}
                  {!isExpanded ? (
                    <span className="max-w-xs truncate text-xs text-slate-400">
                      {section.content.split("\n")[0]?.slice(0, 60) ?? ""}
                    </span>
                  ) : null}
                </div>

                <div className="flex items-center gap-1">
                  {!disabled ? (
                    <>
                      <button
                        className="rounded p-1 text-slate-400 transition-colors hover:text-slate-600"
                        onClick={(e) => {
                          e.stopPropagation();
                          startEditingTagName(section);
                        }}
                        title="Renombrar etiqueta"
                        type="button"
                      >
                        <PencilIcon />
                      </button>
                      <button
                        className="rounded p-1 text-slate-400 transition-colors hover:text-red-500"
                        onClick={(e) => {
                          e.stopPropagation();
                          removeSection(section.id);
                        }}
                        title="Eliminar seccion"
                        type="button"
                      >
                        <TrashIcon />
                      </button>
                    </>
                  ) : null}
                  <span
                    className={[
                      "ml-1 text-slate-400 transition-transform",
                      isExpanded ? "rotate-180" : ""
                    ].join(" ")}
                  >
                    <ChevronDownIcon />
                  </span>
                </div>
              </div>

              {/* Content */}
              {isExpanded ? (
                <div className="border-t border-border-subtle p-3 pl-4">
                  <AutoResizeTextarea
                    className="min-h-[100px] w-full rounded-lg border border-border-subtle bg-slate-50 px-3 py-2 font-mono text-sm leading-relaxed text-slate-700 transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    disabled={disabled}
                    onChange={(e) => {
                      updateSectionContent(section.id, e.target.value);
                    }}
                    spellCheck={false}
                    value={section.content}
                  />
                </div>
              ) : null}
            </div>
          );
        })}

        {sections.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-400">
            No hay secciones. Agrega una con el boton de arriba o escribe en vista raw.
          </p>
        ) : null}
      </div>

      {/* Closing wrapper indicator */}
      {wrapperTagName !== null ? (
        <div className="mt-3 flex items-center gap-2 text-xs text-slate-400">
          <div className="h-px flex-1 bg-slate-200" />
          <span className="font-mono">&lt;/{wrapperTagName}&gt;</span>
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Auto-resize textarea
// ---------------------------------------------------------------------------

function AutoResizeTextarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const ref = reactModule.useRef<HTMLTextAreaElement>(null);

  reactModule.useEffect(() => {
    const el = ref.current;
    if (el !== null) {
      el.style.height = "auto";
      el.style.height = `${el.scrollHeight}px`;
    }
  }, [props.value]);

  return <textarea {...props} ref={ref} />;
}

// ---------------------------------------------------------------------------
// Inline SVG icons (small, no external dependency)
// ---------------------------------------------------------------------------

function ChevronDownIcon() {
  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
      <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ChevronUpIcon() {
  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
      <path d="M18 15l-6-6-6 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
      <path d="M12 5v14m-7-7h14" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function TextIcon() {
  return (
    <svg
      className="h-4 w-4 text-slate-400"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      viewBox="0 0 24 24"
    >
      <path d="M4 7V4h16v3M9 20h6M12 4v16" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PencilIcon() {
  return (
    <svg
      className="h-3.5 w-3.5"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      viewBox="0 0 24 24"
    >
      <path
        d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg
      className="h-3.5 w-3.5"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      viewBox="0 0 24 24"
    >
      <path
        d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6h14z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
