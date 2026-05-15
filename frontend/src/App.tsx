import { useState } from "react";
import "./styles.css";

/**
 * Resultado devuelto por /query o por el contexto de /rag.
 */
interface SearchResult {
  document_id?: string;
  document_version_id?: string;

  title?: string;
  document_title?: string;

  chunk_id?: string;
  chunk_index?: number;
  chunk_position?: number;

  chunk_content?: string;
  content?: string;
  excerpt?: string;

  distance_value?: number;
  similarity_score?: number;
  textual_score?: number;
  hybrid_score?: number;

  match_source?: string;
  source?: string;

  ranking_score?: number;
  ranking_position?: number;

  relevance_label?: string;
  relevance_explanation?: string;

  score?: number;
  ranking?: string;
}

/**
 * Cita documental usada por el flujo RAG.
 */
interface Citation {
  citation_id?: number | string;

  document_title?: string;
  title?: string;

  chunk_id?: string;
  chunk_position?: number;
  chunk_index?: number;

  relevance_score?: number | string;
  score?: number | string;
  ranking_score?: number | string;
  ranking_position?: number;
  relevance_label?: string;

  excerpt?: string;
  source_excerpt?: string;
  chunk_content?: string;
  content?: string;
}

/**
 * Métricas devueltas por el backend.
 */
interface UsageMetrics {
  total_latency_ms?: number;
  retrieval_latency_ms?: number;
  llm_latency_ms?: number;

  prompt_tokens_estimated?: number;
  answer_tokens_estimated?: number;
  total_tokens_estimated?: number;

  estimated_cost_eur?: number;
}

/**
 * Evento analítico básico.
 *
 * Se incluyen campos de tracking normal y también campos preparados
 * para Power BI por si el backend devuelve datos normalizados.
 */
interface AnalyticsEvent {
  id?: string;
  event_id?: string;

  event_type?: string;
  source?: string;

  created_at?: string;
  event_date?: string;
  event_hour?: number;

  query?: string;
  query_text?: string;

  search_mode?: string;
  results_count?: number;

  payload?: {
    query?: string;
    search_mode?: string;
    results_count?: number;
    retrieved_chunks?: number;
    used_context_chunks?: number;
    total_tokens_estimated?: number;
    estimated_cost_eur?: number;
  };
}

/**
 * Componente principal del frontend.
 */
function App() {
  const API_BASE_URL = "http://localhost:8000";

  const [token, setToken] = useState("");
  const [query, setQuery] = useState("");
  const [metadataFilter, setMetadataFilter] = useState("");
  const [limit, setLimit] = useState(3);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [emptyResults, setEmptyResults] = useState(false);

  const [results, setResults] = useState<SearchResult[]>([]);

  const [ragAnswer, setRagAnswer] = useState("");
  const [ragStatus, setRagStatus] = useState("");
  const [citations, setCitations] = useState<Citation[]>([]);
  const [metrics, setMetrics] = useState<UsageMetrics>({});

  const [events, setEvents] = useState<AnalyticsEvent[]>([]);
  const [showEvents, setShowEvents] = useState(false);

  /**
   * Limpia estados visuales comunes.
   */
  const resetVisualState = () => {
    setError("");
    setEmptyResults(false);
  };

  /**
   * Limpia la zona de resultados RAG/búsqueda.
   *
   * No borra nada del backend. Solo limpia lo que se ve en pantalla.
   */
  const clearQueryView = () => {
    setRagAnswer("");
    setRagStatus("");
    setCitations([]);
    setMetrics({});
    setResults([]);
    setEmptyResults(false);
  };

  /**
   * Oculta la tabla de eventos cuando se vuelve a una búsqueda/RAG.
   */
  const hideEventsView = () => {
    setShowEvents(false);
    setEvents([]);
  };

  /**
   * Convierte el filtro escrito por el usuario en metadata_filters.
   */
  const buildMetadataFilters = () => {
    if (!metadataFilter.trim()) {
      return null;
    }

    return {
      category: metadataFilter.trim(),
    };
  };

  /**
   * Devuelve el título de un resultado.
   */
  const getResultTitle = (result: SearchResult) => {
    return result.document_title || result.title || "Documento";
  };

  /**
   * Devuelve el texto principal de un resultado.
   */
  const getResultText = (result: SearchResult) => {
    return (
      result.chunk_content ||
      result.content ||
      result.excerpt ||
      "Sin contenido disponible"
    );
  };

  /**
   * Devuelve el título de una cita.
   */
  const getCitationTitle = (citation: Citation) => {
    return citation.document_title || citation.title || "Documento citado";
  };

  /**
   * Devuelve el extracto de una cita.
   */
  const getCitationText = (citation: Citation) => {
    return (
      citation.excerpt ||
      citation.source_excerpt ||
      citation.chunk_content ||
      citation.content ||
      "Sin extracto disponible"
    );
  };

  /**
   * Devuelve la consulta asociada a un evento.
   */
  const getEventQuery = (event: AnalyticsEvent) => {
    return (
      event.query_text ||
      event.query ||
      event.payload?.query ||
      "-"
    );
  };

  /**
   * Devuelve el modo de búsqueda asociado a un evento.
   */
  const getEventSearchMode = (event: AnalyticsEvent) => {
    return event.search_mode || event.payload?.search_mode || "-";
  };

  /**
   * Devuelve el número de resultados/chunks asociado a un evento.
   */
  const getEventResultsCount = (event: AnalyticsEvent) => {
    return (
      event.results_count ??
      event.payload?.results_count ??
      event.payload?.used_context_chunks ??
      event.payload?.retrieved_chunks ??
      "-"
    );
  };

  /**
   * Busca un chunk recuperado que coincida con una cita.
   */
  const findMatchingChunk = (
    citation: Citation,
    contextResults: SearchResult[],
  ) => {
    return contextResults.find((chunk) => {
      const sameChunkId =
        citation.chunk_id &&
        chunk.chunk_id &&
        citation.chunk_id === chunk.chunk_id;

      const sameChunkIndex =
        citation.chunk_index !== undefined &&
        chunk.chunk_index !== undefined &&
        citation.chunk_index === chunk.chunk_index;

      const sameChunkPosition =
        citation.chunk_position !== undefined &&
        chunk.chunk_position !== undefined &&
        citation.chunk_position === chunk.chunk_position;

      const sameTitle =
        getCitationTitle(citation) === getResultTitle(chunk);

      return sameChunkId || ((sameChunkIndex || sameChunkPosition) && sameTitle);
    });
  };

  /**
   * Ejecuta búsqueda híbrida tradicional contra /query.
   */
  const handleSearch = async () => {
    resetVisualState();
    clearQueryView();
    hideEventsView();

    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          query,
          search_mode: "hybrid",
          limit,
          metadata_filters: buildMetadataFilters(),
        }),
      });

      if (!response.ok) {
        throw new Error("Error realizando la búsqueda.");
      }

      const data = await response.json();

      const nextResults = data.results || [];

      setResults(nextResults);

      if (nextResults.length === 0) {
        setEmptyResults(true);
      }
    } catch (err) {
      setError("No se pudo realizar la búsqueda.");
    } finally {
      setLoading(false);
    }
  };

  /**
   * Ejecuta el flujo RAG contra /rag.
   */
  const handleRagQuery = async () => {
    resetVisualState();
    clearQueryView();
    hideEventsView();

    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/rag`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          query,
          limit,
        }),
      });

      if (!response.ok) {
        throw new Error("Error ejecutando RAG.");
      }

      const data = await response.json();

      const contextResults: SearchResult[] =
        data.context ||
        data.context_chunks ||
        data.results ||
        data.retrieved_chunks ||
        [];

      /**
       * Enriquecemos citas con el contenido del chunk recuperado.
       * Esto evita que el frontend muestre "Sin extracto disponible"
       * cuando el backend devuelve la cita sin excerpt.
       */
      const enrichedCitations: Citation[] = (data.citations || []).map(
        (citation: Citation) => {
          const matchingChunk = findMatchingChunk(citation, contextResults);

          return {
            ...citation,
            document_title:
              citation.document_title ||
              citation.title ||
              matchingChunk?.document_title ||
              matchingChunk?.title,
            excerpt:
              citation.excerpt ||
              citation.source_excerpt ||
              citation.chunk_content ||
              citation.content ||
              matchingChunk?.chunk_content ||
              matchingChunk?.content ||
              matchingChunk?.excerpt ||
              "Sin extracto disponible",
            relevance_score:
              citation.relevance_score ??
              citation.score ??
              citation.ranking_score ??
              matchingChunk?.ranking_score ??
              matchingChunk?.similarity_score ??
              "-",
          };
        },
      );

      setRagAnswer(data.answer || "");
      setRagStatus(data.answer_status || "");
      setCitations(enrichedCitations);
      setMetrics(data.usage_metrics || {});
      setResults(contextResults);

      if (
        !data.answer &&
        contextResults.length === 0 &&
        enrichedCitations.length === 0
      ) {
        setEmptyResults(true);
      }
    } catch (err) {
      setError("No se pudo ejecutar la consulta RAG.");
    } finally {
      setLoading(false);
    }
  };

  /**
   * Obtiene eventos analíticos recientes.
   *
   * Al pulsar "Ver eventos" se limpia la pantalla de búsqueda/RAG
   * y se muestra únicamente la tabla de eventos.
   */
  const handleLoadEvents = async () => {
    resetVisualState();
    clearQueryView();

    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/tracking/events`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error("Error obteniendo eventos.");
      }

      const data = await response.json();

      const nextEvents = Array.isArray(data)
        ? data
        : data.events || data.items || [];

      setEvents(nextEvents);
      setShowEvents(true);

      if (nextEvents.length === 0) {
        setEmptyResults(true);
      }
    } catch (err) {
      setError("No se pudieron cargar los eventos.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <h1>Archivum · Frontend avanzado RAG</h1>

      <div className="card">
        <h2>Configuración</h2>

        <label>Token JWT</label>
        <input
          type="text"
          placeholder="Pega aquí el token JWT"
          value={token}
          onChange={(e) => setToken(e.target.value)}
        />

        <label>Consulta</label>
        <input
          type="text"
          placeholder="Ejemplo: vacaciones empleados"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />

        <label>Filtro metadata</label>
        <input
          type="text"
          placeholder="Ejemplo: technical, legal o rrhh"
          value={metadataFilter}
          onChange={(e) => setMetadataFilter(e.target.value)}
        />

        <label>Límite de resultados</label>
        <input
          type="number"
          value={limit}
          min={1}
          max={10}
          onChange={(e) => setLimit(Number(e.target.value))}
        />

        <div className="button-group">
          <button onClick={handleSearch}>Ejecutar búsqueda</button>
          <button onClick={handleRagQuery}>Ejecutar RAG</button>
          <button onClick={handleLoadEvents}>Ver eventos</button>
        </div>
      </div>

      {loading && (
        <div className="status loading">Procesando consulta...</div>
      )}

      {error && <div className="status error">{error}</div>}

      {emptyResults && (
        <div className="status empty">No se encontraron resultados.</div>
      )}

      {ragAnswer && (
        <div className="card">
          <h2>Respuesta generada</h2>

          <p className="chunk">{ragAnswer}</p>

          <p>
            <strong>Estado:</strong> {ragStatus || "-"}
          </p>
        </div>
      )}

      {Object.keys(metrics).length > 0 && (
        <div className="card">
          <h2>Métricas</h2>

          <ul>
            <li>Latencia total: {metrics.total_latency_ms ?? "-"} ms</li>
            <li>
              Latencia retrieval: {metrics.retrieval_latency_ms ?? "-"} ms
            </li>
            <li>Latencia LLM: {metrics.llm_latency_ms ?? "-"} ms</li>
            <li>Tokens prompt: {metrics.prompt_tokens_estimated ?? "-"}</li>
            <li>Tokens respuesta: {metrics.answer_tokens_estimated ?? "-"}</li>
            <li>Tokens totales: {metrics.total_tokens_estimated ?? "-"}</li>
            <li>Coste estimado: {metrics.estimated_cost_eur ?? "-"} €</li>
          </ul>
        </div>
      )}

      {citations.length > 0 && (
        <div className="card">
          <h2>Citas documentales</h2>

          {citations.map((citation, index) => (
            <div
              key={citation.citation_id || citation.chunk_id || index}
              className="citation-card"
            >
              <h3>{getCitationTitle(citation)}</h3>

              <p>
                <strong>Chunk:</strong>{" "}
                {citation.chunk_position ?? citation.chunk_index ?? "-"}
              </p>

              <p>
                <strong>Score:</strong>{" "}
                {citation.relevance_score ??
                  citation.score ??
                  citation.ranking_score ??
                  "-"}
              </p>

              <p className="chunk">{getCitationText(citation)}</p>
            </div>
          ))}
        </div>
      )}

      {results.length > 0 && (
        <div className="card">
          <h2>Resultados / Contexto recuperado</h2>

          {results.map((result, index) => (
            <div key={result.chunk_id || index} className="result-card">
              <h3>{getResultTitle(result)}</h3>

              <p className="chunk">{getResultText(result)}</p>

              <div className="result-metadata">
                <span>
                  <strong>Posición:</strong>{" "}
                  {result.ranking_position ?? "-"}
                </span>

                <span>
                  <strong>Ranking:</strong>{" "}
                  {result.relevance_label ?? result.ranking ?? "-"}
                </span>

                <span>
                  <strong>Score:</strong>{" "}
                  {result.ranking_score ?? result.score ?? "-"}
                </span>

                <span>
                  <strong>Similitud:</strong>{" "}
                  {result.similarity_score ?? "-"}
                </span>

                <span>
                  <strong>Híbrido:</strong> {result.hybrid_score ?? "-"}
                </span>

                <span>
                  <strong>Origen:</strong>{" "}
                  {result.match_source ?? result.source ?? "-"}
                </span>
              </div>

              {result.relevance_explanation && (
                <p className="explanation">{result.relevance_explanation}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {showEvents && events.length > 0 && (
        <div className="card">
          <h2>Eventos recientes</h2>

          <table>
            <thead>
              <tr>
                <th>Tipo</th>
                <th>Consulta</th>
                <th>Modo</th>
                <th>Resultados</th>
                <th>Fecha</th>
              </tr>
            </thead>

            <tbody>
              {events.map((event, index) => (
                <tr key={event.id || event.event_id || index}>
                  <td>{event.event_type || "-"}</td>
                  <td>{getEventQuery(event)}</td>
                  <td>{getEventSearchMode(event)}</td>
                  <td>{getEventResultsCount(event)}</td>
                  <td>{event.created_at || event.event_date || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default App;