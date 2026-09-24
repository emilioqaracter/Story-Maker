import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router";

import { RequestForm } from "../../commons/change-request/RequestForm";
import { Failed } from "../../commons/shell/Failed";
import { NotFound } from "../../commons/shell/NotFound";
import { saveLastVersion, saveReadingPosition } from "../../commons/storage/local";
import { Prose } from "../../commons/text/Prose";
import { Loading } from "../../commons/ui/State";
import { parseVersion, useChapterAt, useManifest, type SceneAt } from "../data";
import { anchorFromSelection, type FragmentAnchor } from "../requests/anchor";
import { SCENE_ATTRIBUTE } from "./attribute";
import { Navigation } from "./Navigation";

/** Las escenas en orden, cada una en su contenedor con su identificador (RF-180) y su marca (RF-185). */
export function Scenes({
  scenes,
  previous,
}: {
  scenes: readonly Pick<SceneAt, "scene_id" | "scene_number" | "text" | "changed">[];
  previous?: ReadonlyMap<string, string>;
}) {
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set());
  return (
    <>
      {scenes.map((scene) => {
        const before = previous?.get(scene.scene_id);
        const showing = open.has(scene.scene_id) && before !== undefined;
        return (
          <section
            key={scene.scene_id}
            id={`scene-${scene.scene_id}`}
            className={scene.changed ? "scene changed" : "scene"}
            {...{ [SCENE_ATTRIBUTE]: scene.scene_id }}
          >
            <h3 className="scene-heading">
              Escena {scene.scene_number}
              {scene.changed && <span className="mark"> · cambiada en esta versión</span>}
            </h3>
            {scene.changed && before !== undefined && (
              <button
                type="button"
                className="link-button"
                onClick={() =>
                  setOpen((o) => {
                    const n = new Set(o);
                    if (n.has(scene.scene_id)) n.delete(scene.scene_id);
                    else n.add(scene.scene_id);
                    return n;
                  })
                }
              >
                {showing ? "Ocultar la versión anterior" : "Ver la versión anterior al lado"}
              </button>
            )}
            {showing ? (
              <div className="compare">
                <div>
                  <p className="hint">Versión anterior</p>
                  <Prose text={before} />
                </div>
                <div>
                  <p className="hint">Esta versión</p>
                  <Prose text={scene.text} />
                </div>
              </div>
            ) : (
              <Prose text={scene.text} />
            )}
          </section>
        );
      })}
    </>
  );
}

/** `/novels/{id}/v/{v}/chapters/{n}`: la lectura de un capitulo en una version. */
export function Chapter() {
  const params = useParams();
  const novel = params.id ?? "";
  const version = parseVersion(params.v);
  const number = /^\d+$/.test(params.n ?? "") ? Number(params.n) : null;
  if (version === null || number === null || number < 1) return <NotFound />;
  return <ChapterView key={`${novel}/${version}/${number}`} novel={novel} version={version} number={number} />;
}

function ChapterView({ novel, version, number }: { novel: string; version: number; number: number }) {
  const chapter = useChapterAt(novel, version, number);
  const manifest = useManifest(novel, version);
  const changed = chapter.state === "ok" && chapter.data.scenes.some((s) => s.changed);
  const previous = useChapterAt(novel, version > 1 && changed ? version - 1 : version, number);
  const [anchor, setAnchor] = useState<FragmentAnchor | null>(null);
  const [asking, setAsking] = useState<FragmentAnchor | null>(null);

  useEffect(() => {
    if (chapter.state === "ok") {
      saveReadingPosition(novel, version, { chapter: number });
      saveLastVersion(novel, version);
    }
  }, [chapter.state, novel, version, number]);

  const texts = useMemo(
    () => new Map(chapter.state === "ok" ? chapter.data.scenes.map((s) => [s.scene_id, s.text] as const) : []),
    [chapter],
  );
  const onSelect = useCallback(() => {
    setAnchor(anchorFromSelection(document.getSelection(), texts, version, number));
  }, [texts, version, number]);

  if (chapter.state === "loading") return <Loading>Cargando el capítulo…</Loading>;
  if (chapter.state === "failed") return <Failed failure={chapter.failure} reload={chapter.reload} />;

  const before =
    version > 1 && changed && previous.state === "ok"
      ? new Map(previous.data.scenes.map((s) => [s.scene_id, s.text] as const))
      : undefined;
  const numbers = manifest.state === "ok" ? manifest.data.chapters.map((c) => c.number) : [];
  const current = manifest.state === "ok" ? manifest.data.current : false;

  return (
    <article className="chapter" onMouseUp={onSelect} onKeyUp={onSelect}>
      <p className="version-line">
        <Link to={`/novels/${novel}/v/${version}`}>Índice</Link> · Versión {version}
        {current ? " · vigente" : " · no es la vigente"}
      </p>
      {/* La hoja: papel y tinta en los dos temas, con la medida de lectura (BRAND.md §5). */}
      <div className="sheet">
        <h2>Capítulo {number}</h2>
        <Scenes scenes={chapter.data.scenes} previous={before} />
      </div>
      <Navigation novel={novel} version={version} current={number} chapters={numbers} />
      {anchor && !asking && (
        <div className="selection-bar">
          <span className="quote">«{anchor.quote.length > 80 ? `${anchor.quote.slice(0, 80)}…` : anchor.quote}»</span>
          <button type="button" onClick={() => setAsking(anchor)}>
            Pedir un cambio
          </button>
        </div>
      )}
      {asking && (
        <div className="selection-bar open">
          <RequestForm
            novel={novel}
            anchor={asking}
            context={`«${asking.quote.length > 120 ? `${asking.quote.slice(0, 120)}…` : asking.quote}»`}
            onDone={() => {
              setAsking(null);
              setAnchor(null);
            }}
          />
        </div>
      )}
    </article>
  );
}
