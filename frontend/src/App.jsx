import React, { useState } from 'react'
import { Auth } from './Auth'

const pages = [
  'Home',
  'Design Workspace',
  'Truth Table Viewer',
  'Verilog Viewer',
  'Vivado Reports',
  'Documentation',
]

const seedDiagram = {
  nodes: [
    { id: 'a', type: 'input', position: { x: 80, y: 120 }, data: { label: 'Prompt' } },
    { id: 'b', type: 'process', position: { x: 300, y: 120 }, data: { label: 'AI Pipeline' } },
    { id: 'c', type: 'output', position: { x: 560, y: 120 }, data: { label: 'Verified Design' } },
  ],
  edges: [
    { id: 'e1', source: 'a', target: 'b' },
    { id: 'e2', source: 'b', target: 'c' },
  ],
}

function formatValue(value) {
  if (value === null || value === undefined) return '-'
  return String(value)
}

function getFpgaRules(result) {
  const profile = (result?.implementation_profile ?? 'combinational').toLowerCase()
  const shared = [
    'Generate only synthesizable Verilog.',
    'Avoid simulation-only constructs unless explicitly requested.',
    'Avoid delays (#), force/release, and initial blocks for hardware logic.',
    'Keep designs Vivado-compatible and FPGA-ready.',
    'Prevent unintended combinational loops and multiple drivers.',
  ]
  const sequential = [
    'Use proper clocked logic for sequential circuits.',
    'Use non-blocking assignments (<=) in sequential always blocks.',
    'Generate reset logic when required.',
    'Separate state register, next-state, and output logic for FSMs.',
    'Use parameter or localparam state encoding where appropriate.',
    'Infer registers, memories, or DSP resources when the design requires them.',
  ]
  const combinational = [
    'Use blocking assignments (=) in combinational always blocks.',
    'Ensure all combinational outputs are assigned.',
    'Avoid latch inference unless explicitly requested.',
    'Prefer direct Boolean equations, gate instances, and mux trees.',
  ]
  return {
    title: profile === 'sequential' ? 'FPGA Implementation Rules for Sequential Designs' : 'FPGA Implementation Rules for Combinational Designs',
    rules: shared.concat(profile === 'sequential' ? sequential : combinational),
  }
}

function TruthTableView({ rows }) {
  const firstRow = rows?.[0]
  const inputKeys = firstRow ? Object.keys(firstRow.inputs ?? {}) : []
  const outputKeys = firstRow ? Object.keys(firstRow.outputs ?? {}) : []

  if (!rows || rows.length === 0) {
    return <div className="empty-state">Generate a design to view the truth table.</div>
  }

  return (
    <div className="truth-table-wrap">
      <table className="truth-table">
        <thead>
          <tr>
            {inputKeys.map((key) => (
              <th key={key}>{key}</th>
            ))}
            {outputKeys.map((key) => (
              <th key={key}>{key}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {inputKeys.map((key) => (
                <td key={key}>{formatValue(row.inputs?.[key])}</td>
              ))}
              {outputKeys.map((key) => (
                <td key={key}>{formatValue(row.outputs?.[key])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function DiagramView({ result }) {
  const diagram = result?.diagram_json
  const nodes = diagram?.nodes ?? []
  const edges = diagram?.edges ?? []
  const abstraction = result?.abstraction ?? 'transistor_level'

  if (!diagram || nodes.length === 0) {
    return <div className="empty-state">Generate a design to view the schematic.</div>
  }

  return (
    <div className="diagram-shell">
      <div className="diagram-meta">
        <span className="chip chip-static">{diagram.title}</span>
        <span className="chip chip-static">{abstraction.replace('_', ' ')}</span>
      </div>

      {diagram.svg ? (
        <div className="svg-frame">
          <div
            className="diagram-svg diagram-svg-inline"
            style={{ width: '100%', aspectRatio: `${diagram.svg_width || 1280} / ${diagram.svg_height || 720}` }}
            dangerouslySetInnerHTML={{ __html: diagram.svg }}
          />
        </div>
      ) : (
        <div className="svg-frame">
          <svg viewBox="0 0 900 360" className="diagram-svg">
            <defs>
              <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#93a7ca" />
              </marker>
            </defs>
            {edges.map((edge) => {
              const source = nodes.find((node) => node.id === edge.source)
              const target = nodes.find((node) => node.id === edge.target)
              if (!source || !target) return null
              const x1 = source.position.x + 120
              const y1 = source.position.y + 34
              const x2 = target.position.x
              const y2 = target.position.y + 34
              return (
                <line
                  key={edge.id}
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke="#93a7ca"
                  strokeWidth="2"
                  markerEnd="url(#arrow)"
                />
              )
            })}
            {nodes.map((node) => (
              <g key={node.id} transform={`translate(${node.position.x}, ${node.position.y})`}>
                <rect
                  width="120"
                  height="68"
                  rx="16"
                  fill={node.type === 'input' ? 'rgba(109, 214, 255, 0.16)' : node.type === 'output' ? 'rgba(143, 123, 255, 0.18)' : 'rgba(255, 255, 255, 0.06)'}
                  stroke="#2f4875"
                />
                <text x="60" y="38" textAnchor="middle" fill="#e8eefc" fontSize="14">
                  {node.data?.label ?? node.id}
                </text>
              </g>
            ))}
          </svg>
        </div>
      )}
    </div>
  )
}

function TransistorSchematicView({ pmos, nmos, inputs, outputLabel }) {
  const width = 980
  const height = 520
  const left = 90
  const right = 890
  const topRailY = 70
  const bottomRailY = 450
  const pmosY = 165
  const nmosY = 340
  const outputX = 760
  const inputXs = inputs.length === 1 ? [220] : inputs.map((_, index) => 220 + index * 180)

  const branchSpacing = 90
  const branchWidth = 110

  const branchPositions = (count, baseY) =>
    Array.from({ length: Math.max(count, 1) }, (_, index) => ({
      x: 260 + index * branchSpacing,
      y: baseY,
    }))

  const pmosPositions = branchPositions(pmos.length, pmosY)
  const nmosPositions = branchPositions(nmos.length, nmosY)

  const renderTransistor = (tx, index, rowY, positions, tint) => {
    const pos = positions[index] ?? positions[0]
    const gateX = inputXs[index % inputXs.length]
    const sourceX = pos.x - branchWidth / 2
    const drainX = pos.x + branchWidth / 2
    const bodyY = rowY - 24
    const bodyHeight = 48
    const gateY = rowY

    return (
      <g key={tx.name}>
        <line x1={gateX} y1={gateY} x2={sourceX - 22} y2={gateY} stroke="#93a7ca" strokeWidth="2" />
        <line x1={sourceX} y1={gateY} x2={sourceX} y2={bodyY} stroke="#93a7ca" strokeWidth="2" />
        <line x1={drainX} y1={gateY} x2={drainX} y2={bodyY + bodyHeight} stroke="#93a7ca" strokeWidth="2" />
        <rect
          x={sourceX}
          y={bodyY}
          width={branchWidth}
          height={bodyHeight}
          rx="12"
          fill={tint}
          stroke="#2f4875"
          strokeWidth="2"
        />
        <line x1={gateX} y1={gateY - 24} x2={gateX} y2={gateY + 24} stroke="#e8eefc" strokeWidth="3" />
        <text x={pos.x} y={rowY - 36} textAnchor="middle" fill="#e8eefc" fontSize="13">
          {tx.name}
        </text>
        <text x={pos.x} y={rowY + 36} textAnchor="middle" fill="#93a7ca" fontSize="12">
          {formatValue(tx.gate)}
        </text>
        <text x={sourceX} y={bodyY - 6} textAnchor="start" fill="#93a7ca" fontSize="11">
          {formatValue(tx.source)}
        </text>
        <text x={drainX} y={bodyY + bodyHeight + 16} textAnchor="end" fill="#93a7ca" fontSize="11">
          {formatValue(tx.drain)}
        </text>
      </g>
    )
  }

  return (
    <div className="svg-frame schematic-frame">
      <svg viewBox={`0 0 ${width} ${height}`} className="diagram-svg cmos-svg">
        <defs>
          <marker id="schematic-dot" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5">
            <circle cx="5" cy="5" r="4" fill="#93a7ca" />
          </marker>
        </defs>

        <line x1={left} y1={topRailY} x2={right} y2={topRailY} stroke="#6dd6ff" strokeWidth="4" />
        <text x={left} y={topRailY - 12} fill="#6dd6ff" fontSize="14" fontWeight="700">
          VDD
        </text>

        <line x1={left} y1={bottomRailY} x2={right} y2={bottomRailY} stroke="#93a7ca" strokeWidth="4" />
        <text x={left} y={bottomRailY + 24} fill="#93a7ca" fontSize="14" fontWeight="700">
          GND
        </text>

        <line x1={760} y1={topRailY} x2={760} y2={bottomRailY} stroke="#93a7ca" strokeWidth="2" strokeDasharray="8 8" />
        <circle cx={760} cy={260} r="8" fill="#8f7bff" />
        <text x={780} y={264} fill="#e8eefc" fontSize="13">
          {outputLabel}
        </text>

        {inputs.map((input, index) => {
          const x = inputXs[index] ?? inputXs[0]
          return (
            <g key={input}>
              <line x1={x} y1={105} x2={x} y2={160} stroke="#6dd6ff" strokeWidth="2" markerEnd="url(#schematic-dot)" />
              <text x={x} y={95} textAnchor="middle" fill="#6dd6ff" fontSize="13">
                {input}
              </text>
            </g>
          )
        })}

        <text x="120" y="125" fill="#e8eefc" fontSize="13" fontWeight="700">
          PMOS Network
        </text>
        <text x="120" y="300" fill="#e8eefc" fontSize="13" fontWeight="700">
          NMOS Network
        </text>

        {pmos.map((tx, index) => renderTransistor(tx, index, pmosY, pmosPositions, 'rgba(109, 214, 255, 0.14)'))}
        {nmos.map((tx, index) => renderTransistor(tx, index, nmosY, nmosPositions, 'rgba(143, 123, 255, 0.14)'))}

        <line x1={740} y1={topRailY} x2={760} y2={225} stroke="#6dd6ff" strokeWidth="2" />
        <line x1={740} y1={bottomRailY} x2={760} y2={295} stroke="#93a7ca" strokeWidth="2" />
      </svg>
      <div className="schematic-caption">
        PMOS pull-up network on top, NMOS pull-down network on bottom.
      </div>
    </div>
  )
}

export function App() {
  const [activePage, setActivePage] = useState('Home')
  const [sessionEmail, setSessionEmail] = useState('')
  const [prompt, setPrompt] = useState('Design a NAND gate')
  const [modelingStyle, setModelingStyle] = useState('dataflow')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()
  const designEndpoint = apiBaseUrl ? `${apiBaseUrl.replace(/\/$/, '')}/api/design` : '/api/design'

  const modelingModes = [
    { key: 'dataflow', label: 'Data Flow', hint: 'Use continuous assignments and expressions.' },
    { key: 'behavioral', label: 'Behavioral', hint: 'Use always blocks and case statements.' },
    { key: 'gate_level', label: 'Gate Level', hint: 'Use primitive gates like and, or, not.' },
    { key: 'structural', label: 'Structural', hint: 'Use module instances and wiring.' },
  ]

  const handleGenerate = async () => {
    setLoading(true)
    setError('')

    try {
      const response = await fetch(designEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prompt,
          email: sessionEmail || null,
          design_hint: 'auto',
          modeling_style: modelingStyle,
          validate_vivado: true,
        }),
      })

      if (!response.ok) {
        let detail = ''
        try {
          const payload = await response.json()
          detail = payload?.detail ? `: ${payload.detail}` : ''
        } catch {
          const text = await response.text()
          detail = text.trim() ? `: ${text.trim()}` : ''
        }
        throw new Error(`Backend returned ${response.status}${detail}`)
      }

      const data = await response.json()
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate design')
    } finally {
      setLoading(false)
    }
  }

  if (!sessionEmail) {
    return <Auth onLogin={setSessionEmail} />
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <div>
            <p className="eyebrow">AI Hardware Design Copilot</p>
            <h1>Prompt to verified circuits</h1>
          </div>
          <nav>
            {pages.map((page) => (
              <button
                key={page}
                className={page === activePage ? 'nav-item active' : 'nav-item'}
                onClick={() => setActivePage(page)}
              >
                {page}
              </button>
            ))}
          </nav>
          <div style={{ marginTop: 'auto', paddingTop: '20px', borderTop: '1px solid var(--panel-border)' }}>
            <p className="eyebrow" style={{ marginBottom: '8px' }}>Logged in as</p>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.85rem', color: 'var(--muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '160px' }}>{sessionEmail}</span>
              <button className="logout-btn" style={{ marginLeft: '10px' }} onClick={() => setSessionEmail('')}>Logout</button>
            </div>
          </div>
        </div>
      </aside>
      <main className="content">
        <section className="hero">
          <p className="eyebrow">Workspace</p>
          <h2>{activePage}</h2>
            <p>
              This shell is ready for the backend workflow, Verilog generation styles, truth table
              views, FPGA implementation rules, and Vivado report panels.
            </p>
        </section>

        <section className="panel grid">
          <div>
            <h3>AI Chat Interface</h3>
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              rows={6}
              placeholder="Describe a circuit to begin..."
            />
            <div className="action-row">
              <button className="generate-button" onClick={handleGenerate} disabled={loading}>
                {loading ? 'Generating...' : 'Generate'}
              </button>
              {error ? <span className="error-text">{error}</span> : null}
            </div>
          </div>
          <div>
            <h3 style={{ marginTop: '20px' }}>Modeling Style</h3>
            <div className="modeling-grid">
              {modelingModes.map((mode) => (
                <button
                  key={mode.key}
                  className={mode.key === modelingStyle ? 'modeling-button active' : 'modeling-button'}
                  onClick={() => setModelingStyle(mode.key)}
                >
                  <span>{mode.label}</span>
                  <small>{mode.hint}</small>
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="panel grid">
          <div>
            <h3>Design Summary</h3>
            <div className="summary-grid">
              <div className="summary-card"><span>Design</span><strong>{formatValue(result?.design_name)}</strong></div>
              <div className="summary-card"><span>Type</span><strong>{formatValue(result?.design_type)}</strong></div>
              <div className="summary-card"><span>Abstraction</span><strong>{formatValue(result?.abstraction)}</strong></div>
              <div className="summary-card"><span>Modeling</span><strong>{formatValue(result?.modeling_style)}</strong></div>
              <div className="summary-card"><span>Gate Count</span><strong>{formatValue(result?.gate_count)}</strong></div>
              <div className="summary-card"><span>Tech Node</span><strong>{formatValue(result?.technology_node)}</strong></div>
              <div className="summary-card"><span>Equation</span><strong>{formatValue(result?.boolean_equation)}</strong></div>
            </div>
          </div>
          <div>
            <h3>Truth Table</h3>
            <TruthTableView rows={result?.truth_table ?? []} />
          </div>
        </section>

        <section className="panel">
          <h3>Retrieved Knowledge</h3>
          {result?.knowledge_contexts?.length ? (
            <div className="knowledge-grid">
              {result.knowledge_contexts.map((item, index) => (
                <article key={`${item.source}-${index}`} className="knowledge-card">
                  <div className="knowledge-card-head">
                    <strong>{item.title}</strong>
                    <span>{item.source}</span>
                  </div>
                  <p>{item.snippet}</p>
                </article>
              ))}
            </div>
          ) : (
            <div className="empty-state">Run a design to see retrieved knowledge snippets here.</div>
          )}
        </section>

        <section className="panel">
          <h3>Verilog</h3>
          <pre>{result?.verilog ?? 'Generate a design to view Verilog here.'}</pre>
        </section>

        <section className="panel">
          <h3>Vivado Testbench</h3>
          <pre>{result?.testbench ?? 'Generate a design to view the Vivado testbench here.'}</pre>
        </section>

        <section className="panel">
          <h3>{getFpgaRules(result).title}</h3>
          <div className="requirements-grid">
            {getFpgaRules(result).rules.map((item) => (
              <div key={item} className="requirement-card">
                {item}
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <h3>Vivado Reports</h3>
          <div className="summary-grid">
            <div className="summary-card"><span>Timing</span><strong>{formatValue(result?.vivado_results?.timing_report?.status)}</strong></div>
            <div className="summary-card"><span>Utilization</span><strong>{formatValue(result?.vivado_results?.utilization_report?.status)}</strong></div>
            <div className="summary-card"><span>Power</span><strong>{formatValue(result?.vivado_results?.power_report?.status)}</strong></div>
          </div>
          <div className="vivado-diagnostics">
            <details>
              <summary>Timing details</summary>
              <pre>{JSON.stringify(result?.vivado_results?.timing_report ?? {}, null, 2)}</pre>
            </details>
            <details>
              <summary>Utilization details</summary>
              <pre>{JSON.stringify(result?.vivado_results?.utilization_report ?? {}, null, 2)}</pre>
            </details>
            <details>
              <summary>Power details</summary>
              <pre>{JSON.stringify(result?.vivado_results?.power_report ?? {}, null, 2)}</pre>
            </details>
          </div>
        </section>

        <section className="panel">
          <h3>Documentation</h3>
          <div className="doc-box">{result?.documentation ?? 'Generate a design to view documentation here.'}</div>
        </section>
      </main>
    </div>
  )
}
