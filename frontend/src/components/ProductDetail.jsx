import React, { useState, useEffect } from 'react';

export default function ProductDetail({ product, botUsername, onClose }) {
  const fotos = product.fotos?.length ? product.fotos : (product.foto_path ? [product.foto_path] : []);
  const [activePhoto, setActivePhoto] = useState(fotos[0] || null);
  const [imgError, setImgError] = useState({});

  // Reset photo when product changes
  useEffect(() => {
    setActivePhoto(fotos[0] || null);
    setImgError({});
  }, [product.id]);

  const tgLink = `https://t.me/${botUsername}?start=producto_${product.id}`;
  const refLabel = `#${String(product.id).padStart(4, '0')}`;

  const handleImgError = (src) => {
    setImgError(prev => ({ ...prev, [src]: true }));
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
        {/* Close */}
        <button className="modal-close" onClick={onClose} aria-label="Cerrar">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>

        <div className="modal-inner">
          {/* ── Gallery ── */}
          <div className="modal-gallery">
            <div className="gallery-main-img">
              {activePhoto && !imgError[activePhoto] ? (
                <img
                  src={activePhoto}
                  alt={product.nombre}
                  onError={() => handleImgError(activePhoto)}
                />
              ) : (
                <div className="gallery-no-img">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                    <rect x="3" y="3" width="18" height="18" rx="2"/>
                    <circle cx="8.5" cy="8.5" r="1.5"/>
                    <polyline points="21 15 16 10 5 21"/>
                  </svg>
                  <span>Sin imagen disponible</span>
                </div>
              )}
            </div>

            {fotos.length > 1 && (
              <div className="gallery-thumbs">
                {fotos.map((foto, i) => (
                  <button
                    key={i}
                    className={`thumb-btn${activePhoto === foto ? ' active' : ''}`}
                    onClick={() => setActivePhoto(foto)}
                    aria-label={`Foto ${i + 1}`}
                  >
                    {!imgError[foto] ? (
                      <img
                        src={foto}
                        alt={`Foto ${i + 1}`}
                        onError={() => handleImgError(foto)}
                      />
                    ) : (
                      <div style={{
                        width:'100%', height:'100%',
                        background:'var(--gray-200)',
                        display:'flex', alignItems:'center', justifyContent:'center',
                        fontSize:'.65rem', color:'var(--gray-400)'
                      }}>
                        {i + 1}
                      </div>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* ── Info ── */}
          <div className="modal-info">
            <div>
              <p className="modal-ref">{refLabel}</p>
              <h2 className="modal-name">{product.nombre}</h2>
            </div>

            {(product.liga || product.equipo) && (
              <div className="modal-tags">
                {product.liga && <span className="tag">{product.liga}</span>}
                {product.equipo && <span className="tag blue">{product.equipo}</span>}
              </div>
            )}

            {/* Price table */}
            <div className="price-table">
              <p className="price-table-title">Opciones de precio</p>
              <div className="price-row">
                <span className="price-row-label">Sin personalización</span>
                <span className="price-row-value highlighted">18€</span>
              </div>
              <div className="price-divider" />
              <div className="price-row">
                <span className="price-row-label">Con nombre y número</span>
                <span className="price-row-value">21€</span>
              </div>
              <div className="price-divider" />
              <div className="price-row">
                <span className="price-row-label">Con nombre, número y parches</span>
                <span className="price-row-value">22€</span>
              </div>
            </div>

            {/* Personalization info */}
            <div>
              <p className="modal-section-title">Personalización</p>
              <p className="modal-section-text">
                Puedes añadir nombre y número de dorsal, así como parches oficiales
                (Liga, Champions, Mundial…). Indícalo al hacer el pedido por Telegram.
              </p>
            </div>

            <div className="modal-divider" />

            {/* Shipping info */}
            <div>
              <p className="modal-section-title">Envío</p>
              <p className="modal-section-text">
                Envío a toda España. Tiempo estimado: 10–15 días hábiles
                desde la confirmación del pago.
              </p>
            </div>

            {/* CTA */}
            <a
              className="btn-telegram"
              href={tgLink}
              target="_blank"
              rel="noopener noreferrer"
            >
              <svg viewBox="0 0 24 24">
                <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12L7.17 13.954l-2.96-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.978.605z"/>
              </svg>
              Pedir por Telegram
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
