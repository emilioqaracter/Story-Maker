import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";

import { api } from "../api/client";
import { settle } from "../api/errors";
import { usePolled } from "../api/poll";
import { describeRun } from "../api/run-state";
import { visitedInterviews, visitedNovels } from "../storage/local";

/**
 * Portada de la aplicacion (RF-166): las novelas de RI-37 con su estado y sus
 * versiones, y el acceso a encargar una nueva. Si la lista no se puede leer,
 * quedan las que este navegador ha visitado (RD-29, D-61), y la pantalla lo dice.
 */
export function Home() {
  const list = usePolled(
    "novels",
    () => settle(() => api.GET("/novels")),
    () => false,
  );
  const interviews = visitedInterviews();
  const [id, setId] = useState("");
  const navigate = useNavigate();

  const open = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = id.trim();
    if (trimmed) void navigate(`/novels/${encodeURIComponent(trimmed)}`);
  };

  return (
    <section>
      <h1>Novelas</h1>
      <p>
        <Link to="/new" className="primary-link">
          Encargar una novela nueva
        </Link>
      </p>
      {list.state === "ok" ? (
        list.data.novels.length === 0 ? (
          <p>Todavía no hay ninguna novela.</p>
        ) : (
          <ul className="novel-list">
            {list.data.novels.map((n) => (
              <li key={n.novel_id}>
                <Link to={`/novels/${n.novel_id}`}>{n.title}</Link>
                <span className="meta">
                  {" "}
                  · {n.versions === 1 ? "1 versión" : `${n.versions} versiones`} · {describeRun(n.state)}
                </span>
              </li>
            ))}
          </ul>
        )
      ) : list.state === "failed" ? (
        <Visited />
      ) : (
        <p className="loading">Cargando las novelas…</p>
      )}
      {interviews.length > 0 && (
        <>
          <h2>Entrevistas empezadas</h2>
          <ul>
            {interviews.map((i) => (
              <li key={i}>
                <Link to={`/interviews/${i}`}>Seguir la entrevista {i}</Link>
              </li>
            ))}
          </ul>
        </>
      )}
      <form onSubmit={open} className="open-novel">
        <label>
          Abrir una novela por su identificador
          <input value={id} onChange={(e) => setId(e.target.value)} placeholder="por ejemplo, real" />
        </label>
        <button type="submit">Abrir</button>
      </form>
    </section>
  );
}

function Visited() {
  const novels = visitedNovels();
  return (
    <>
      <p className="hint">No se pudo leer la lista de novelas del backend (RI-37). Estas son las que has abierto en este navegador.</p>
      {novels.length === 0 ? (
        <p>Todavía no has abierto ninguna.</p>
      ) : (
        <ul className="novel-list">
          {novels.map((n) => (
            <li key={n}>
              <Link to={`/novels/${n}`}>{n}</Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
