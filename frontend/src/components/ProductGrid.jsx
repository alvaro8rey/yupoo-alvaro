import React from 'react';
import ProductCard from './ProductCard.jsx';

export default function ProductGrid({ products, loading, error, onClear, hasFilter, onSelect }) {
  if (loading) {
    return (
      <div className="product-grid">
        <div className="state-center">
          <div className="spinner" />
          <p>Cargando catálogo...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="product-grid">
        <div className="state-center">
          <div className="empty-icon">⚠️</div>
          <h3>Error al cargar el catálogo</h3>
          <p>No se pudo obtener la lista de productos. Verifica que <code>data.json</code> exista en <code>public/</code>.</p>
          <p style={{ fontSize: '.8rem', color: 'var(--gray-400)', marginTop: '-.25rem' }}>{error}</p>
        </div>
      </div>
    );
  }

  if (products.length === 0) {
    return (
      <div className="product-grid">
        <div className="state-center">
          <div className="empty-icon">👕</div>
          <h3>No se encontraron camisetas</h3>
          <p>
            {hasFilter
              ? 'Prueba con otro filtro o equipo.'
              : 'Todavía no hay productos disponibles.'}
          </p>
          {hasFilter && (
            <button className="clear-btn" onClick={onClear}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
              Ver todos
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="product-grid">
      {products.map(product => (
        <ProductCard
          key={product.id}
          product={product}
          onClick={() => onSelect(product)}
        />
      ))}
    </div>
  );
}
