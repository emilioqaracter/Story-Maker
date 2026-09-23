import { Link } from "react-router";

/** Anterior y siguiente entre los capitulos congelados, e indice (RF-181). Pura. */
export function neighbours(chapters: readonly number[], current: number): { previous?: number; next?: number } {
  const sorted = [...chapters].sort((a, b) => a - b);
  const previous = sorted.filter((n) => n < current).at(-1);
  const next = sorted.find((n) => n > current);
  return { ...(previous !== undefined && { previous }), ...(next !== undefined && { next }) };
}

export function Navigation({
  novel,
  version,
  current,
  chapters,
}: {
  novel: string;
  version: number;
  current: number;
  chapters: readonly number[];
}) {
  const { previous, next } = neighbours(chapters, current);
  const base = `/novels/${novel}/v/${version}`;
  return (
    <nav className="chapter-nav" aria-label="Capítulos">
      {previous !== undefined ? <Link to={`${base}/chapters/${previous}`}>← Capítulo {previous}</Link> : <span />}
      <Link to={base}>Índice</Link>
      {next !== undefined ? <Link to={`${base}/chapters/${next}`}>Capítulo {next} →</Link> : <span />}
    </nav>
  );
}
