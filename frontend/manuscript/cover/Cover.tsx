import { useEffect } from "react";
import { Link, useParams } from "react-router";

import { useRunState } from "../../commons/api/run-state";
import { currentVersion, useVersions } from "../../commons/api/versions";
import { Failed } from "../../commons/shell/Failed";
import { NotFound } from "../../commons/shell/NotFound";
import { readingPosition, rememberNovel } from "../../commons/storage/local";
import { Loading } from "../../commons/ui/State";
import { parseVersion, useManifest } from "../data";
import { Toc } from "../toc/Toc";
import { changedChapters } from "../versions/marks";
import { VersionPicker } from "../versions/VersionPicker";

/**
 * `/novels/{id}` y `/novels/{id}/v/{v}`: portada e indice (RF-177, RF-182 a RF-184).
 *
 * Sin `v`, la version vigente. Titulo, dedicatoria y destinatario salen del
 * manifiesto de RI-43; la version que se lee se dice siempre, y si no es la
 * vigente tambien.
 */
export function Cover() {
  const params = useParams();
  const novel = params.id ?? "";
  if (params.v !== undefined && parseVersion(params.v) === null) return <NotFound />;
  return <CoverView key={novel} novel={novel} asked={parseVersion(params.v)} />;
}

function CoverView({ novel, asked }: { novel: string; asked: number | null }) {
  const run = useRunState(novel);
  const versions = useVersions(novel);
  const version = asked ?? (versions.state === "ok" ? currentVersion(versions.data.versions) : null);
  const manifest = useManifest(novel, version);

  useEffect(() => {
    if (run.state === "ok") rememberNovel(novel);
  }, [run.state, novel]);

  if (run.state === "failed") return <Failed failure={run.failure} reload={run.reload} />;
  if (versions.state === "failed") return <Failed failure={versions.failure} reload={versions.reload} />;
  if (manifest.state === "failed") return <Failed failure={manifest.failure} reload={manifest.reload} />;
  if (run.state === "loading" || versions.state === "loading" || manifest.state !== "ok" || version === null) {
    return <Loading>Cargando la novela…</Loading>;
  }

  const m = manifest.data;
  const info = versions.data.versions.find((v) => v.number === version);
  const cambiados = changedChapters(m.chapters);
  const position = readingPosition(novel, version);
  return (
    <article className="cover">
      <header className="cover-header">
        <p className="version-line">
          Versión {version}
          {m.current ? " · vigente" : " · no es la vigente"}
        </p>
        <h1>{m.title}</h1>
        {m.dedication && <p className="dedication">{m.dedication}</p>}
        {m.recipient_name && <p className="hint">Una novela para {m.recipient_name}</p>}
        {info && info.cause != null && (
          <p className="changes-line">
            {cambiados.length === 1 ? "Cambió 1 capítulo" : `Cambiaron ${cambiados.length} capítulos`} respecto a la versión{" "}
            {version - 1}, por la <Link to={`/novels/${novel}/changes`}>solicitud nº {info.cause}</Link>.
          </p>
        )}
        <VersionPicker novel={novel} versions={versions.data.versions} reading={version} />
        {position !== undefined && (
          <p className="continue">
            <Link to={`/novels/${novel}/v/${version}/chapters/${position.chapter}`} className="button-primary">
              Seguir leyendo: capítulo {position.chapter}
            </Link>
          </p>
        )}
        <p className="cover-links">
          <Link to={`/novels/${novel}/bible`} className="button-link">
            Personajes y lugares
          </Link>
          <Link to={`/novels/${novel}/changes`} className="button-link">
            Solicitudes de cambio
          </Link>
        </p>
      </header>
      <Toc novel={novel} version={version} chapters={m.chapters} run={run.data} />
    </article>
  );
}
