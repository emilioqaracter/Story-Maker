import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { api } from "../commons/api/client";
import { settle, type Failure } from "../commons/api/errors";
import { Failed } from "../commons/shell/Failed";
import { rememberInterview } from "../commons/storage/local";

/**
 * `/new` (RF-167): crea una entrevista con RI-38 y lleva a su direccion. La
 * entrevista vive en el backend, no en la pestana: volver a su direccion la
 * reanuda. La referencia evita crear dos si React monta dos veces.
 */
export function NewInterview() {
  const navigate = useNavigate();
  const started = useRef(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void settle(() => api.POST("/interviews")).then((outcome) => {
      if (outcome.ok) {
        rememberInterview(outcome.data.interview_id);
        void navigate(`/interviews/${outcome.data.interview_id}`, { replace: true });
      } else {
        started.current = false;
        setFailure(outcome.failure);
      }
    });
  }, [navigate, attempt]);

  if (failure) return <Failed failure={failure} reload={() => (setFailure(null), setAttempt((n) => n + 1))} />;
  return <p className="loading">Preparando la entrevista…</p>;
}
