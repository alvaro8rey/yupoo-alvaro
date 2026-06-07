import React, { useState, useEffect } from 'react';

/* ── Inline SVG logos ── */
const LaLigaLogo = () => <img src="/logos/laliga.png" alt="La Liga" style={{width:'100%',height:'100%',objectFit:'contain'}} />;

const PremierLogo = () => (
  <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <rect width="100" height="100" rx="14" fill="#37003C"/>
    <polygon points="50,12 54,24 67,24 57,32 61,44 50,36 39,44 43,32 33,24 46,24" fill="#00FF85"/>
    <ellipse cx="50" cy="62" rx="18" ry="22" fill="#00FF85"/>
    <circle cx="50" cy="55" r="13" fill="#00FF85"/>
    <circle cx="50" cy="53" r="16" fill="#00D672" opacity="0.35"/>
    <circle cx="45" cy="52" r="2.5" fill="#37003C"/>
    <circle cx="55" cy="52" r="2.5" fill="#37003C"/>
    <ellipse cx="50" cy="58" rx="2.5" ry="2" fill="#37003C" opacity="0.5"/>
    <rect x="38" y="72" width="10" height="10" rx="5" fill="#00FF85"/>
    <rect x="52" y="72" width="10" height="10" rx="5" fill="#00FF85"/>
  </svg>
);

const BundesligaLogo = () => (
  <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <rect width="100" height="33" rx="0" fill="#1a1a1a"/><rect x="0" y="0" width="100" height="33" rx="14" fill="#1a1a1a"/>
    <rect x="0" y="33" width="100" height="34" fill="#d3010c"/>
    <rect x="0" y="67" width="100" height="33" fill="#ffce00"/><rect x="0" y="67" width="100" height="33" rx="14" fill="#ffce00"  style={{clipPath:'inset(0 0 0 0 round 0 0 14px 14px)'}}/>
    <rect width="100" height="100" rx="14" fill="none" stroke="white" strokeWidth="0"/>
    <circle cx="50" cy="50" r="28" fill="#d3010c" opacity="0.9"/>
    <text x="50" y="61" fontFamily="Arial Black,sans-serif" fontSize="38" fontWeight="900" fill="white" textAnchor="middle">B</text>
  </svg>
);

const SerieALogo = () => (
  <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <rect width="100" height="100" rx="14" fill="#1a1a2e"/>
    <path d="M50,10 L80,22 L80,58 Q78,80 50,92 Q22,80 20,58 L20,22 Z" fill="#0b5394"/>
    <path d="M50,10 L80,22 L80,58 Q78,80 50,92 Q22,80 20,58 L20,22 Z" fill="none" stroke="#4fc3f7" strokeWidth="2"/>
    <text x="50" y="52" fontFamily="Arial Black,sans-serif" fontSize="22" fontWeight="900" fill="white" textAnchor="middle">Serie</text>
    <text x="50" y="72" fontFamily="Arial Black,sans-serif" fontSize="22" fontWeight="900" fill="#f5c518" textAnchor="middle">A</text>
  </svg>
);

const Ligue1Logo = () => (
  <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <rect width="100" height="100" rx="14" fill="#091d40"/>
    <rect x="10" y="10" width="36" height="80" rx="6" fill="#e8351c"/>
    <rect x="54" y="10" width="36" height="80" rx="6" fill="#e8351c"/>
    <rect x="10" y="10" width="36" height="36" rx="6" fill="#0055a4"/>
    <rect x="54" y="54" width="36" height="36" rx="6" fill="#0055a4"/>
    <text x="28" y="86" fontFamily="Arial Black,sans-serif" fontSize="11" fontWeight="900" fill="white" textAnchor="middle">L1</text>
  </svg>
);

const SeleccionesLogo = () => (
  <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <rect width="100" height="100" rx="14" fill="#1565c0"/>
    <circle cx="50" cy="50" r="32" fill="#1976d2"/>
    <ellipse cx="50" cy="50" rx="14" ry="32" fill="none" stroke="white" strokeWidth="1.5" opacity="0.6"/>
    <line x1="18" y1="50" x2="82" y2="50" stroke="white" strokeWidth="1.5" opacity="0.6"/>
    <path d="M22,34 Q50,40 78,34" stroke="white" strokeWidth="1.5" fill="none" opacity="0.6"/>
    <path d="M22,66 Q50,60 78,66" stroke="white" strokeWidth="1.5" fill="none" opacity="0.6"/>
    <circle cx="50" cy="50" r="32" fill="none" stroke="white" strokeWidth="1.5" opacity="0.5"/>
    <ellipse cx="40" cy="44" rx="9" ry="7" fill="#43a047" opacity="0.9"/>
    <ellipse cx="58" cy="46" rx="7" ry="6" fill="#43a047" opacity="0.9"/>
    <ellipse cx="50" cy="58" rx="6" ry="5" fill="#388e3c" opacity="0.8"/>
  </svg>
);

const MundialLogo = () => <img src="/logos/mundial.png" alt="Mundial 2026" style={{width:'100%',height:'100%',objectFit:'contain'}} />;

const LEAGUE_LOGO_COMPONENTS = {
  'la liga':        LaLigaLogo,
  'premier league': PremierLogo,
  'bundesliga':     BundesligaLogo,
  'serie a':        SerieALogo,
  'ligue 1':        Ligue1Logo,
  'selecciones':    SeleccionesLogo,
  'mundial 2026':   MundialLogo,
  'mundial':        MundialLogo,
};

function LeagueIcon({ liga }) {
  const key = (liga || '').toLowerCase().trim();
  const Logo = LEAGUE_LOGO_COMPONENTS[key];
  if (Logo) {
    return <span className="league-icon"><Logo /></span>;
  }
  return <span className="league-icon">⚽</span>;
}

export default function Sidebar({ leagueTree, filter, onSelect, isOpen }) {
  const [openLeagues, setOpenLeagues] = useState({});

  useEffect(() => {
    if (filter?.liga) {
      setOpenLeagues(prev => ({ ...prev, [filter.liga]: true }));
    }
  }, [filter]);

  const toggleLeague = (liga) => {
    setOpenLeagues(prev => ({ ...prev, [liga]: !prev[liga] }));
  };

  const isAllActive = !filter;

  return (
    <aside className={`sidebar${isOpen ? ' open' : ''}`}>
      <div className="sidebar-section">
        <button
          className={`sidebar-all-btn${isAllActive ? ' active' : ''}`}
          onClick={() => onSelect(null)}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="7" height="7" rx="1"/>
            <rect x="14" y="3" width="7" height="7" rx="1"/>
            <rect x="3" y="14" width="7" height="7" rx="1"/>
            <rect x="14" y="14" width="7" height="7" rx="1"/>
          </svg>
          Todos los productos
        </button>
      </div>

      {leagueTree.length > 0 && (
        <>
          <div className="sidebar-divider" />
          <p className="sidebar-label">Ligas y equipos</p>
        </>
      )}

      {leagueTree.map(({ liga, equipos }) => {
        const isOpen = openLeagues[liga] ?? false;
        const isLeagueActive = filter?.liga === liga && !filter?.equipo;
        const hasActiveChild = filter?.liga === liga;

        return (
          <div className="league-section" key={liga}>
            <button
              className={`league-header${hasActiveChild ? ' has-active' : ''}`}
              onClick={() => toggleLeague(liga)}
            >
              <LeagueIcon liga={liga} />
              <span
                className="league-name"
                onClick={(e) => { e.stopPropagation(); onSelect({ liga }); }}
                style={{ cursor: 'pointer' }}
              >
                {liga}
              </span>
              <span className="league-count">{equipos.length}</span>
              <svg
                className={`league-chevron${isOpen ? ' open' : ''}`}
                viewBox="0 0 24 24" fill="none" stroke="currentColor"
                strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
              >
                <polyline points="6 9 12 15 18 9"/>
              </svg>
            </button>

            {isOpen && (
              <div className="league-teams">
                <button
                  className={`team-btn${isLeagueActive ? ' active' : ''}`}
                  onClick={() => onSelect({ liga })}
                >
                  <span className="team-dot" />
                  Todos en {liga}
                </button>
                {equipos.map(equipo => {
                  const isTeamActive = filter?.liga === liga && filter?.equipo === equipo;
                  return (
                    <button
                      key={equipo}
                      className={`team-btn${isTeamActive ? ' active' : ''}`}
                      onClick={() => onSelect({ liga, equipo })}
                    >
                      <span className="team-dot" />
                      {equipo}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </aside>
  );
}
