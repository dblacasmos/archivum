import { useState } from "react";

/*
  URL base del backend.

  Se obtiene desde variables de entorno para
  evitar hardcodear direcciones dentro del código.
*/
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

/*
  Tipo que representa un resultado real
  devuelto por el backend de Archivum.
*/
interface SearchResult {
  document_id?: string;
  document_version_id?: string;
  title?: string;
  chunk_id?: string;
  chunk_index?: number;
  chunk_content?: string;

  distance_value?: number;

  similarity_score?: number;
  textual_score?: number;
  hybrid_score?: number;

  match_source?: string;

  ranking_score?: number;
  ranking_position?: number;

  relevance_label?: string;
  relevance_explanation?: string;
}

/*
  Componente principal del frontend.
*/
export default function App() {
  /*
    Token JWT pegado manualmente desde Swagger.
  */
  const [token, setToken] = useState("");

  /*
    Texto de búsqueda introducido por el usuario.
  */
  const [query, setQuery] = useState("");

  /*
    Tipo de búsqueda seleccionado.
  */
  const [searchType, setSearchType] = useState("hybrid");

  /*
    Número máximo de resultados.
  */
  const [limit, setLimit] = useState(5);

  /*
    Filtro metadata simple.

    Ejemplo:
    category=legal
  */
  const [metadataFilter, setMetadataFilter] = useState("");

  /*
    Resultados recuperados desde backend.
  */
  const [results, setResults] = useState<SearchResult[]>([]);

  /*
    Estado visual de carga.
  */
  const [loading, setLoading] = useState(false);

  /*
    Mensaje de error mostrado al usuario.
  */
  const [error, setError] = useState("");

  /*
    Ejecuta la búsqueda contra FastAPI.
  */
  async function executeSearch() {
    try {
      /*
        Activamos loading.
      */
      setLoading(true);

      /*
        Limpiamos errores anteriores.
      */
      setError("");

      /*
        Objeto metadata_filters esperado
        por el backend.
      */
      const filters: Record<string, string> = {};

      /*
        Convierte:
        category=legal

        en:
        {
          category: "legal"
        }
      */
      if (metadataFilter.includes("=")) {
        const [key, value] = metadataFilter.split("=");

        filters[key.trim()] = value.trim();
      }

      /*
        Petición HTTP POST al endpoint /query.
      */
      const response = await fetch(`${API_URL}/query`, {
        method: "POST",

        headers: {
          "Content-Type": "application/json",

          /*
            Token JWT para autenticación.
          */
          Authorization: `Bearer ${token}`
        },

        /*
          Body JSON enviado al backend.
        */
        body: JSON.stringify({
          query,

          /*
            Campo esperado realmente
            por el backend.
          */
          search_mode: searchType,

          limit,

          /*
            Metadata enviada correctamente.
          */
          metadata_filters:
            Object.keys(filters).length > 0
              ? filters
              : null
        })
      });

      /*
        Si backend devuelve error HTTP.
      */
      if (!response.ok) {
        throw new Error("Error realizando la búsqueda");
      }

      /*
        Convertimos respuesta JSON.
      */
      const data = await response.json();

      /*
        Guardamos resultados.
      */
      setResults(data.results || []);
    } catch (err) {
      /*
        Error visual simple.
      */
      setError("No se pudo completar la búsqueda");
    } finally {
      /*
        Desactivamos loading.
      */
      setLoading(false);
    }
  }

  /*
    Render principal del frontend.
  */
  return (
    <div className="page">
      <div className="container">
        <h1>Archivum Search</h1>

        <p className="subtitle">
          Interfaz básica de búsqueda documental
        </p>

        <div className="card">
          <label>Token JWT</label>

          <textarea
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Pega aquí tu token JWT"
          />

          <label>Consulta</label>

          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ejemplo: contrato laboral"
          />

          <label>Modo de búsqueda</label>

          <select
            value={searchType}
            onChange={(e) => setSearchType(e.target.value)}
          >
            <option value="semantic">
              Semántica
            </option>

            <option value="hybrid">
              Híbrida
            </option>
          </select>

          <label>Límite de resultados</label>

          <input
            type="number"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
          />

          <label>Filtro metadata</label>

          <input
            type="text"
            value={metadataFilter}
            onChange={(e) =>
              setMetadataFilter(e.target.value)
            }
            placeholder="category=legal"
          />

          <button onClick={executeSearch}>
            {loading ? "Buscando..." : "Buscar"}
          </button>

          {error && (
            <div className="error">
              {error}
            </div>
          )}
        </div>

        <div className="results">
          {results.map((result, index) => (
            <div
              className="result-card"
              key={result.chunk_id || index}
            >
              <h2>
                {result.title || "Documento"}
              </h2>

              <p className="chunk">
                {result.chunk_content}
              </p>

              <div className="meta">
                <span>
                  Posición:{" "}
                  {result.ranking_position ?? "-"}
                </span>

                <span>
                  Ranking:{" "}
                  {result.relevance_label ?? "-"}
                </span>

                <span>
                  Score ranking:{" "}
                  {result.ranking_score ?? "-"}
                </span>

                <span>
                  Similitud:{" "}
                  {result.similarity_score ?? "-"}
                </span>

                <span>
                  Híbrido:{" "}
                  {result.hybrid_score ?? "-"}
                </span>

                <span>
                  Origen:{" "}
                  {result.match_source ?? "-"}
                </span>
              </div>

              <p className="explanation">
                {result.relevance_explanation}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}