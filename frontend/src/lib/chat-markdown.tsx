import React from "react";

/**
 * Minimal markdown renderer for chatbot replies.
 * Handles: **bold**, # headings, - bullets, 1. numbered lists, --- rules,
 * | pipe tables (header row bold, cells joined for narrow bubbles).
 * Builds React elements directly — never HTML strings — so neither user
 * nor LLM text can inject markup.
 */

function inline(text: string, keyPrefix: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const re = /\*\*([^*]+)\*\*/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    nodes.push(<strong key={`${keyPrefix}-b${i++}`}>{m[1]}</strong>);
    last = m.index + m[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

const isSepRow = (cells: string[]) =>
  cells.every((c) => /^:?-{3,}:?$/.test(c));

export function ChatMarkdown({ text }: { text: string }) {
  const lines = text.replace(/\r/g, "").split("\n");
  const out: React.ReactNode[] = [];
  let bullets: string[] = [];
  let nums: string[] = [];
  let table: string[][] = [];
  let key = 0;

  const flush = () => {
    if (bullets.length) {
      const items = bullets;
      bullets = [];
      out.push(
        <ul key={`ul-${key++}`} className="list-disc space-y-0.5 pl-4">
          {items.map((b, i) => (
            <li key={i}>{inline(b, `ul${key}-${i}`)}</li>
          ))}
        </ul>,
      );
    }
    if (nums.length) {
      const items = nums;
      nums = [];
      out.push(
        <ol key={`ol-${key++}`} className="list-decimal space-y-0.5 pl-4">
          {items.map((b, i) => (
            <li key={i}>{inline(b, `ol${key}-${i}`)}</li>
          ))}
        </ol>,
      );
    }
    if (table.length) {
      const rows = table.filter((r) => !isSepRow(r));
      table = [];
      rows.forEach((cells, ri) => {
        out.push(
          ri === 0 ? (
            <p key={`th-${key++}`} className="mt-1 font-semibold">
              {cells.map((c, ci) => (
                <React.Fragment key={ci}>
                  {ci > 0 ? " · " : ""}
                  {inline(c, `th${key}-${ci}`)}
                </React.Fragment>
              ))}
            </p>
          ) : (
            <p key={`tr-${key++}`} className="text-foreground/90">
              {cells.map((c, ci) => (
                <React.Fragment key={ci}>
                  {ci > 0 ? " · " : ""}
                  {inline(c, `tr${key}-${ci}`)}
                </React.Fragment>
              ))}
            </p>
          ),
        );
      });
    }
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (/^\s*[-*]\s+/.test(line)) {
      flush();
      bullets.push(line.replace(/^\s*[-*]\s+/, ""));
      continue;
    }
    if (/^\s*\d+[.)]\s+/.test(line)) {
      flush();
      nums.push(line.replace(/^\s*\d+[.)]\s+/, ""));
      continue;
    }
    if (/^\s*\|.*\|\s*$/.test(line)) {
      flush();
      table.push(
        line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim()),
      );
      continue;
    }
    flush();
    if (!line.trim()) continue;
    if (/^#{1,4}\s/.test(line)) {
      out.push(
        <p key={`h-${key++}`} className="mt-1 font-bold">
          {inline(line.replace(/^#{1,4}\s*/, ""), `h${key}`)}
        </p>,
      );
    } else if (/^(---|___|\*\*\*)\s*$/.test(line)) {
      out.push(<hr key={`hr-${key++}`} className="my-1.5 border-border" />);
    } else {
      out.push(
        <p key={`p-${key++}`} className="whitespace-pre-wrap">
          {inline(line, `p${key}`)}
        </p>,
      );
    }
  }
  flush();

  return <>{out}</>;
}
