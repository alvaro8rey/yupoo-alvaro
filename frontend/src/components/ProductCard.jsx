import React, { useState } from 'react';

export default function ProductCard({ product, onClick }) {
  const [imgError, setImgError] = useState(false);

  const coverPhoto = product.fotos?.[0] || product.foto_path || '';
  const hasImage = coverPhoto && !imgError;

  return (
    <article className="product-card" onClick={onClick} role="button" tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}>
      <div className="card-image-wrap">
        {hasImage ? (
          <img
            src={coverPhoto}
            alt={product.nombre}
            loading="lazy"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="card-no-img">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <rect x="3" y="3" width="18" height="18" rx="2"/>
              <circle cx="8.5" cy="8.5" r="1.5"/>
              <polyline points="21 15 16 10 5 21"/>
            </svg>
            <span>Sin imagen</span>
          </div>
        )}
        <span className="card-ref-badge">#{String(product.id).padStart(4, '0')}</span>
      </div>

      <div className="card-body">
        {product.equipo && (
          <p className="card-equipo">{product.equipo}</p>
        )}
        <p className="card-name">{product.nombre}</p>
        <p className="card-price">
          Desde {product.precio ?? 18}€
          <span>/ unidad</span>
        </p>
      </div>
    </article>
  );
}
