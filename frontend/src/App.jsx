import React, { useState, useEffect, useMemo, useCallback } from 'react';
import Sidebar from './components/Sidebar.jsx';
import ProductGrid from './components/ProductGrid.jsx';
import ProductDetail from './components/ProductDetail.jsx';

// ── Config ────────────────────────────────────────────────────────────────────
const BOT_USERNAME = "tu_bot"; // ← change this
const STORE_NAME = "Camisetas Premium";
// ─────────────────────────────────────────────────────────────────────────────

export default function App() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [search, setSearch] = useState('');
  // filter: null = all, { liga } = by league, { liga, equipo } = by team
  const [filter, setFilter] = useState(null);

  const [selectedProduct, setSelectedProduct] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Load data
  useEffect(() => {
    fetch('/data.json')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        setProducts(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  // Close sidebar on resize to desktop
  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth > 768) setSidebarOpen(false);
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  // ESC to close modal
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') setSelectedProduct(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Prevent body scroll when modal open
  useEffect(() => {
    document.body.style.overflow = selectedProduct ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [selectedProduct]);

  // Build league/team tree from products
  const leagueTree = useMemo(() => {
    const map = {};
    for (const p of products) {
      const liga = p.liga || 'Sin categoría';
      const equipo = p.equipo || 'Otros';
      if (!map[liga]) map[liga] = new Set();
      map[liga].add(equipo);
    }
    return Object.entries(map).map(([liga, equipos]) => ({
      liga,
      equipos: Array.from(equipos).sort(),
    })).sort((a, b) => a.liga.localeCompare(b.liga));
  }, [products]);

  // Filtered products
  const filtered = useMemo(() => {
    let list = products;
    if (filter) {
      if (filter.equipo) {
        list = list.filter(p => p.liga === filter.liga && p.equipo === filter.equipo);
      } else {
        list = list.filter(p => p.liga === filter.liga);
      }
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter(p =>
        p.nombre.toLowerCase().includes(q) ||
        (p.equipo && p.equipo.toLowerCase().includes(q)) ||
        (p.liga && p.liga.toLowerCase().includes(q))
      );
    }
    return list;
  }, [products, filter, search]);

  const handleSelectFilter = useCallback((f) => {
    setFilter(f);
    setSidebarOpen(false);
  }, []);

  const handleClearFilters = useCallback(() => {
    setFilter(null);
    setSearch('');
  }, []);

  return (
    <div className="app-wrapper">
      {/* ── Header ── */}
      <header className="header">
        <div className="header-left">
          <button
            className="hamburger"
            onClick={() => setSidebarOpen(s => !s)}
            aria-label="Toggle menu"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              {sidebarOpen
                ? <><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></>
                : <><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></>
              }
            </svg>
          </button>
          <span className="store-name">
            {STORE_NAME.split(' ')[0]} <span>{STORE_NAME.split(' ').slice(1).join(' ')}</span>
          </span>
        </div>

        <div className="header-search">
          <svg className="header-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            type="text"
            placeholder="Buscar camisetas, equipos..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {search && (
            <button className="search-clear" onClick={() => setSearch('')} aria-label="Clear search">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          )}
        </div>
      </header>

      <div className="app-body">
        {/* ── Sidebar overlay (mobile) ── */}
        {sidebarOpen && (
          <div
            className="sidebar-overlay"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* ── Sidebar ── */}
        <Sidebar
          leagueTree={leagueTree}
          filter={filter}
          onSelect={handleSelectFilter}
          isOpen={sidebarOpen}
        />

        {/* ── Main ── */}
        <main className="main-content">
          <div className="results-bar">
            <p className="results-info">
              <strong>{filtered.length}</strong> producto{filtered.length !== 1 ? 's' : ''}
              {filter && (
                <> en <span style={{color:'var(--blue-dark)',fontWeight:700}}>{filter.equipo || filter.liga}</span></>
              )}
              {search && (
                <> para &ldquo;<span style={{color:'var(--blue-dark)',fontWeight:700}}>{search}</span>&rdquo;</>
              )}
            </p>
            {(filter || search) && (
              <span className="active-filter-tag">
                {filter ? (filter.equipo || filter.liga) : search}
                <button onClick={handleClearFilters} aria-label="Clear filter">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </span>
            )}
          </div>

          <ProductGrid
            products={filtered}
            loading={loading}
            error={error}
            onClear={handleClearFilters}
            hasFilter={!!(filter || search)}
            onSelect={setSelectedProduct}
          />
        </main>
      </div>

      {/* ── Detail modal ── */}
      {selectedProduct && (
        <ProductDetail
          product={selectedProduct}
          botUsername={BOT_USERNAME}
          onClose={() => setSelectedProduct(null)}
        />
      )}
    </div>
  );
}
