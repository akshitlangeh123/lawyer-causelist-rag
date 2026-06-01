import { useEffect, useMemo, useState } from "react";
import "./App.css";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function JsonBlock({ data }) {
  return <pre className="json-block">{JSON.stringify(data, null, 2)}</pre>;
}

function SourceList({ sources }) {
  if (!sources || sources.length === 0) return null;

  return (
    <div className="card">
      <h3>Sources</h3>
      <div className="source-list">
        {sources.map((source, index) => (
          <div className="source-card" key={`${source.source_number || index}-${index}`}>
            <div className="source-title">
              {source.source_number || `S${index + 1}`} · {source.source_file || "Unknown file"}
            </div>
            <div className="muted">
              Page: {source.source_page || "N/A"} · Case:{" "}
              {source.case_reference || source.registration_number || "N/A"}
            </div>
            {source.stage && <div className="muted">Stage: {source.stage}</div>}
            {source.text_preview && <p className="preview">{source.text_preview}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}

function App() {
  const [activeTab, setActiveTab] = useState("ask");

  const [health, setHealth] = useState(null);
  const [vectorStatus, setVectorStatus] = useState(null);
  const [llamaStatus, setLlamaStatus] = useState(null);

  const [askQuestion, setAskQuestion] = useState(
    "What is the next hearing date for Complaint/1344/2024?"
  );
  const [askLimit, setAskLimit] = useState(10);
  const [askResult, setAskResult] = useState(null);
  const [askLoading, setAskLoading] = useState(false);

  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploadResults, setUploadResults] = useState([]);

  const [caseQuery, setCaseQuery] = useState("");
  const [listingDate, setListingDate] = useState("");
  const [stage, setStage] = useState("");
  const [caseResults, setCaseResults] = useState(null);

  const [registrationNumber, setRegistrationNumber] = useState("1344/2024");
  const [cnrNumber, setCnrNumber] = useState("");
  const [caseDetailResults, setCaseDetailResults] = useState(null);

  const [semanticQuery, setSemanticQuery] = useState(
    "cases involving POCSO and FIR details"
  );
  const [semanticResults, setSemanticResults] = useState(null);

  const tabs = useMemo(
    () => [
      { id: "ask", label: "Ask" },
      { id: "upload", label: "Upload PDFs" },
      { id: "cases", label: "Cases" },
      { id: "details", label: "Case Details" },
      { id: "semantic", label: "Semantic Search" },
      { id: "status", label: "Status" },
    ],
    []
  );

  async function apiGet(path) {
    const response = await fetch(`${API_BASE}${path}`);
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `GET ${path} failed`);
    }
    return response.json();
  }

  async function apiPost(path, body) {
    const response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `POST ${path} failed`);
    }

    return response.json();
  }

  async function loadStatus() {
    const [healthData, vectorData, llamaData] = await Promise.allSettled([
      apiGet("/health"),
      apiGet("/vector/status"),
      apiGet("/llama/status"),
    ]);

    if (healthData.status === "fulfilled") setHealth(healthData.value);
    if (vectorData.status === "fulfilled") setVectorStatus(vectorData.value);
    if (llamaData.status === "fulfilled") setLlamaStatus(llamaData.value);
  }

  useEffect(() => {
    loadStatus();
  }, []);

  async function handleAsk() {
    setAskLoading(true);
    setAskResult(null);

    try {
      const data = await apiPost("/ask", {
        question: askQuestion,
        limit: Number(askLimit),
      });
      setAskResult(data);
    } catch (error) {
      setAskResult({ error: error.message });
    } finally {
      setAskLoading(false);
    }
  }

  async function handleUpload() {
    if (!selectedFiles.length) {
      setUploadResults([{ error: "Please select at least one PDF." }]);
      return;
    }

    const results = [];

    for (const file of selectedFiles) {
      const formData = new FormData();
      formData.append("file", file);

      try {
        const response = await fetch(`${API_BASE}/documents/upload`, {
          method: "POST",
          body: formData,
        });

        const data = await response.json();

        if (!response.ok) {
          results.push({
            file_name: file.name,
            error: data.detail || "Upload failed",
          });
        } else {
          results.push(data);
        }
      } catch (error) {
        results.push({
          file_name: file.name,
          error: error.message,
        });
      }
    }

    setUploadResults(results);
    loadStatus();
  }

  async function searchCases() {
    const params = new URLSearchParams();

    if (caseQuery) params.set("q", caseQuery);
    if (listingDate) params.set("listing_date", listingDate);
    if (stage) params.set("stage", stage);
    params.set("limit", "50");

    try {
      const data = await apiGet(`/cases?${params.toString()}`);
      setCaseResults(data);
    } catch (error) {
      setCaseResults({ error: error.message });
    }
  }

  async function searchCaseDetails() {
    const params = new URLSearchParams();

    if (registrationNumber) params.set("registration_number", registrationNumber);
    if (cnrNumber) params.set("cnr_number", cnrNumber);
    params.set("limit", "50");

    try {
      const data = await apiGet(`/case-details?${params.toString()}`);
      setCaseDetailResults(data);
    } catch (error) {
      setCaseDetailResults({ error: error.message });
    }
  }

  async function runSemanticSearch() {
    const params = new URLSearchParams();

    params.set("q", semanticQuery);
    params.set("limit", "10");

    try {
      const data = await apiGet(`/semantic-search?${params.toString()}`);
      setSemanticResults(data);
    } catch (error) {
      setSemanticResults({ error: error.message });
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div>
          <h1>Jammu Cause List RAG</h1>
          <p className="muted">Local FastAPI + SQLite + Chroma + Llama assistant</p>
        </div>

        <nav className="tabs">
          {tabs.map((tab) => (
            <button
              className={activeTab === tab.id ? "active" : ""}
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <div className="status-pill">
          API: {health?.status === "ok" ? "Online" : "Unknown"}
        </div>
      </aside>

      <main className="main-content">
        {activeTab === "ask" && (
          <section>
            <h2>Ask a question</h2>
            <p className="muted">
              Uses your Docker backend, local retrieval, and local Llama through Ollama.
            </p>

            <div className="card">
              <label>Question</label>
              <textarea
                value={askQuestion}
                onChange={(event) => setAskQuestion(event.target.value)}
                rows={5}
              />

              <div className="row">
                <div>
                  <label>Limit</label>
                  <input
                    type="number"
                    min="1"
                    max="30"
                    value={askLimit}
                    onChange={(event) => setAskLimit(event.target.value)}
                  />
                </div>
              </div>

              <button onClick={handleAsk} disabled={askLoading}>
                {askLoading ? "Asking..." : "Ask"}
              </button>
            </div>

            {askResult && (
              <>
                <div className="card">
                  <h3>Answer</h3>
                  {askResult.error ? (
                    <p className="error">{askResult.error}</p>
                  ) : (
                    <>
                      <p className="answer">{askResult.answer}</p>
                      <div className="muted">
                        Mode: {askResult.mode} · Evidence: {askResult.evidence_count}
                      </div>
                    </>
                  )}
                </div>

                <SourceList sources={askResult.sources} />
              </>
            )}
          </section>
        )}

        {activeTab === "upload" && (
          <section>
            <h2>Upload PDFs</h2>
            <p className="muted">
              Uploading saves the PDF, parses it, stores records in SQLite, and indexes vector chunks.
            </p>

            <div className="card">
              <input
                type="file"
                accept="application/pdf"
                multiple
                onChange={(event) => setSelectedFiles(Array.from(event.target.files || []))}
              />

              <button onClick={handleUpload}>Upload selected PDFs</button>
            </div>

            {uploadResults.length > 0 && (
              <div className="card">
                <h3>Upload results</h3>
                <JsonBlock data={uploadResults} />
              </div>
            )}
          </section>
        )}

        {activeTab === "cases" && (
          <section>
            <h2>Search cause-list rows</h2>

            <div className="card">
              <label>General query</label>
              <input
                value={caseQuery}
                placeholder="Example: AKASH GUPTA"
                onChange={(event) => setCaseQuery(event.target.value)}
              />

              <div className="grid">
                <div>
                  <label>Listing date</label>
                  <input
                    value={listingDate}
                    placeholder="20-03-2026"
                    onChange={(event) => setListingDate(event.target.value)}
                  />
                </div>

                <div>
                  <label>Stage</label>
                  <input
                    value={stage}
                    placeholder="Prosecution Evidence"
                    onChange={(event) => setStage(event.target.value)}
                  />
                </div>
              </div>

              <button onClick={searchCases}>Search cases</button>
            </div>

            {caseResults && (
              <div className="card">
                <h3>Results</h3>
                <div className="muted">Count: {caseResults.count}</div>
                <JsonBlock data={caseResults.results || caseResults} />
              </div>
            )}
          </section>
        )}

        {activeTab === "details" && (
          <section>
            <h2>Search case details</h2>

            <div className="card">
              <div className="grid">
                <div>
                  <label>Registration number</label>
                  <input
                    value={registrationNumber}
                    placeholder="1344/2024"
                    onChange={(event) => setRegistrationNumber(event.target.value)}
                  />
                </div>

                <div>
                  <label>CNR number</label>
                  <input
                    value={cnrNumber}
                    placeholder="JKJM030067592024"
                    onChange={(event) => setCnrNumber(event.target.value)}
                  />
                </div>
              </div>

              <button onClick={searchCaseDetails}>Search details</button>
            </div>

            {caseDetailResults && (
              <div className="card">
                <h3>Results</h3>
                <div className="muted">Count: {caseDetailResults.count}</div>
                <JsonBlock data={caseDetailResults.results || caseDetailResults} />
              </div>
            )}
          </section>
        )}

        {activeTab === "semantic" && (
          <section>
            <h2>Semantic search</h2>

            <div className="card">
              <label>Semantic query</label>
              <textarea
                value={semanticQuery}
                onChange={(event) => setSemanticQuery(event.target.value)}
                rows={3}
              />

              <button onClick={runSemanticSearch}>Search semantically</button>
            </div>

            {semanticResults && (
              <div className="card">
                <h3>Results</h3>
                <div className="muted">Count: {semanticResults.count}</div>
                <JsonBlock data={semanticResults.results || semanticResults} />
              </div>
            )}
          </section>
        )}

        {activeTab === "status" && (
          <section>
            <h2>Status</h2>

            <div className="grid">
              <div className="card">
                <h3>API</h3>
                <JsonBlock data={health} />
              </div>

              <div className="card">
                <h3>Vector index</h3>
                <JsonBlock data={vectorStatus} />
              </div>

              <div className="card">
                <h3>Llama</h3>
                <JsonBlock data={llamaStatus} />
              </div>
            </div>

            <button onClick={loadStatus}>Refresh status</button>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
