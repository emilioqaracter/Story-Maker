import { Link } from "react-router";

import type { VersionInfo } from "../../commons/api/versions";

/** RF-183. Todas las versiones siguen legibles: la anterior se conserva (D-52). */
export function VersionPicker({ novel, versions, reading }: { novel: string; versions: readonly VersionInfo[]; reading: number }) {
  if (versions.length < 2) return null;
  return (
    <nav className="versions" aria-label="Versiones">
      <span className="hint">Versiones:</span>
      {versions.map((v) => (
        <Link
          key={v.number}
          to={`/novels/${novel}/v/${v.number}`}
          aria-current={v.number === reading ? "page" : undefined}
          className={v.number === reading ? "active" : undefined}
        >
          {v.number}
          {v.current ? " · vigente" : ""}
        </Link>
      ))}
    </nav>
  );
}
