import * as reactModule from "react";

// ---------------------------------------------------------------------------
// Types (local, mirror del parser en XmlTagEditor)
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

// ---------------------------------------------------------------------------
// Parser (duplicado read-only para no romper encapsulamiento de XmlTagEditor)
// ---------------------------------------------------------------------------

const OPEN_TAG_REGEX = /<(\w+)>/g;

let nextSectionId = 0;
function createSectionId(): string {
  nextSectionId += 1;
  return `viewer-section-${nextSectionId}`;
}

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
    if (/^<\/\w+>/.test(stripped)) {
      depth = Math.max(0, depth - 1);
    }
    result.push(indent.repeat(depth) + stripped);
    if (/^<\w+>/.test(stripped) && !stripped.startsWith("</") && !/<\/\w+>\s*$/.test(stripped)) {
      depth += 1;
    }
  }

  return result.join("\n");
}

function parseXmlSections(raw: string): ParsedSection[] {
  const sections: ParsedSection[] = [];
  let cursor = 0;

  while (cursor < raw.length) {
    OPEN_TAG_REGEX.lastIndex = cursor;
    const openMatch = OPEN_TAG_REGEX.exec(raw);

    if (openMatch?.index === undefined) {
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
        break;
      }

      if (nextOpen !== -1 && nextOpen < nextClose) {
        depth += 1;
        searchPos = nextOpen + openTag.length;
      } else {
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

function parseXmlDocument(raw: string): ParseResult {
  const topLevel = parseXmlSections(raw);

  if (topLevel.length === 1 && topLevel[0]?.kind === "tag") {
    const wrapper = topLevel[0];
    const children = parseXmlSections(wrapper.content);
    const tagChildCount = children.filter((c) => c.kind === "tag").length;
    if (tagChildCount >= 2) {
      return { wrapperTagName: wrapper.tagName, sections: children };
    }
  }

  return { wrapperTagName: null, sections: topLevel };
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface XmlTagViewerProps {
  value: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function XmlTagViewer(props: XmlTagViewerProps) {
  const { value } = props;

  const parseResult = reactModule.useMemo<ParseResult>(() => parseXmlDocument(value), [value]);
  const { sections, wrapperTagName } = parseResult;

  const [expandedIds, setExpandedIds] = reactModule.useState<Set<string>>(() => new Set());

  const hasTags = sections.some((s) => s.kind === "tag");

  const toggleSection = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
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

  return (
    <div>
      {/* Toolbar */}
      {hasTags ? (
        <div className="mb-3 flex items-center gap-2">
          <button
            className="flex items-center gap-1 rounded border border-slate-600 bg-slate-700 px-2.5 py-1 text-xs font-medium text-slate-200 transition-colors hover:bg-slate-600"
            onClick={collapseAll}
            type="button"
          >
            <ChevronUpIcon />
            Colapsar todo
          </button>
          <button
            className="flex items-center gap-1 rounded border border-slate-600 bg-slate-700 px-2.5 py-1 text-xs font-medium text-slate-200 transition-colors hover:bg-slate-600"
            onClick={expandAll}
            type="button"
          >
            <ChevronDownIcon />
            Expandir todo
          </button>
        </div>
      ) : null}

      {/* Wrapper indicator */}
      {wrapperTagName !== null ? (
        <div className="mb-2 flex items-center gap-2 text-xs text-slate-500">
          <span className="font-mono">&lt;{wrapperTagName}&gt;</span>
          <div className="h-px flex-1 bg-slate-700" />
        </div>
      ) : null}

      {/* Sections */}
      <div className="space-y-2">
        {sections.map((section) => {
          if (section.kind === "text") {
            return (
              <pre
                className="overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100"
                key={section.id}
              >
                {section.content}
              </pre>
            );
          }

          const isExpanded = expandedIds.has(section.id);

          return (
            <div className="overflow-hidden rounded-lg border border-slate-700" key={section.id}>
              {/* Section header */}
              <button
                className="flex w-full items-center justify-between bg-slate-800 px-3 py-2 text-left transition-colors hover:bg-slate-700"
                onClick={() => {
                  toggleSection(section.id);
                }}
                type="button"
              >
                <span className="flex items-center gap-1.5 font-mono text-xs">
                  <span className="font-bold text-teal-400">&lt;</span>
                  <span className="text-slate-200">{section.tagName}</span>
                  <span className="font-bold text-teal-400">&gt;</span>
                </span>
                {!isExpanded ? (
                  <span className="ml-3 max-w-xs truncate text-xs text-slate-500">
                    {section.content.split("\n")[0]?.slice(0, 60) ?? ""}
                  </span>
                ) : null}
                <span
                  className={[
                    "ml-auto shrink-0 text-slate-400 transition-transform",
                    isExpanded ? "rotate-180" : ""
                  ].join(" ")}
                >
                  <ChevronDownIcon />
                </span>
              </button>

              {/* Section content */}
              {isExpanded ? (
                <pre className="overflow-x-auto bg-slate-900 p-3 text-xs text-slate-100">
                  {section.content}
                </pre>
              ) : null}
            </div>
          );
        })}

        {sections.length === 0 ? (
          <p className="py-4 text-center text-xs text-slate-500">Sin contenido.</p>
        ) : null}
      </div>

      {/* Closing wrapper indicator */}
      {wrapperTagName !== null ? (
        <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
          <div className="h-px flex-1 bg-slate-700" />
          <span className="font-mono">&lt;/{wrapperTagName}&gt;</span>
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Inline SVG icons
// ---------------------------------------------------------------------------

function ChevronDownIcon() {
  return (
    <svg
      className="h-3.5 w-3.5"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      viewBox="0 0 24 24"
    >
      <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ChevronUpIcon() {
  return (
    <svg
      className="h-3.5 w-3.5"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      viewBox="0 0 24 24"
    >
      <path d="M18 15l-6-6-6 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
