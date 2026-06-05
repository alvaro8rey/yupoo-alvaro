import React, { useState, useEffect } from 'react';

const LEAGUE_ICONS = {
  'La Liga': '🇪🇸',
  'Premier League': '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
  'Bundesliga': '🇩🇪',
  'Serie A': '🇮🇹',
  'Ligue 1': '🇫🇷',
  'Selecciones': '🌍',
};

function getIcon(liga) {
  return LEAGUE_ICONS[liga] || '⚽';
}

export default function Sidebar({ leagueTree, filter, onSelect, isOpen }) {
  // Keep leagues open that contain the active filter
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
              <span className="league-icon">{getIcon(liga)}</span>
              <span
                className="league-name"
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect({ liga });
                }}
                style={{ cursor: 'pointer' }}
              >
                {liga}
              </span>
              <span className="league-count">{equipos.length}</span>
              <svg
                className={`league-chevron${isOpen ? ' open' : ''}`}
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polyline points="6 9 12 15 18 9"/>
              </svg>
            </button>

            {isOpen && (
              <div className="league-teams">
                {/* Also option to show all teams in league */}
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
