import React, { useState, useEffect } from 'react';

export default function ProductDetail({ product, botUsername, onClose }) {
  const fotos = product.fotos?.length ? product.fotos : (product.foto_path ? [product.foto_path] : []);
  const [activePhoto, setActivePhoto] = useState(fotos[0] || null);
  const [imgError, setImgError] = useState({});
  const [zoom, setZoom] = useState(false);

  useEffect(() => {
    setActivePhoto(fotos[0] || null);
    setImgError({});
    setZoom(false);
  }, [product.id]);

  const tgLink = `https://t.me/${botUsername}?start=producto_${product.id}`;
  const refLabel = `#${String(product.id).padStart(4, '0')}`;
  const tallas = Array.isArray(product.tallas)
    ? product.tallas
    : JSON.parse(product.tallas || '[]');

  const handleImgError = (src) => setImgError(prev => ({ ...prev, [src]: true }));

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">

        <button className="modal-close" onClick={onClose} aria-label="Cerrar">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>

        <div className="modal-inner">

          {/* ── Galería ── */}
          <div className="modal-gallery">
            <div
              className={`gallery-main-img${zoom ? ' zoomed' : ''}`}
              onClick={() => fotos.length && setZoom(z => !z)}
              title={fotos.length ? 'Clic para ampliar' : ''}
            >
              {activePhoto && !imgError[activePhoto] ? (
                <img src={activePhoto} alt={product.nombre} onError={() => handleImgError(activePhoto)} />
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
              {fotos.length > 0 && !zoom && (
                <div className="gallery-zoom-hint">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                    <line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/>
                  </svg>
                </div>
              )}
            </div>

            {fotos.length > 1 && (
              <div className="gallery-thumbs">
                {fotos.map((foto, i) => (
                  <button
                    key={i}
                    className={`thumb-btn${activePhoto === foto ? ' active' : ''}`}
                    onClick={() => { setActivePhoto(foto); setZoom(false); }}
                    aria-label={`Foto ${i + 1}`}
                  >
                    {!imgError[foto] ? (
                      <img src={foto} alt={`Foto ${i + 1}`} onError={() => handleImgError(foto)} />
                    ) : (
                      <div style={{ width:'100%', height:'100%', background:'var(--gray-200)',
                        display:'flex', alignItems:'center', justifyContent:'center',
                        fontSize:'.65rem', color:'var(--gray-400)' }}>{i + 1}</div>
                    )}
                  </button>
                ))}
              </div>
            )}

            {/* Contador fotos */}
            {fotos.length > 1 && (
              <p className="gallery-count">{fotos.indexOf(activePhoto) + 1} / {fotos.length} fotos</p>
            )}
          </div>

          {/* ── Info ── */}
          <div className="modal-info">

            {/* Cabecera */}
            <div>
              <p className="modal-ref">{refLabel}</p>
              <h2 className="modal-name">{product.nombre}</h2>
              {(product.liga || product.equipo) && (
                <div className="modal-tags" style={{marginTop:'.6rem'}}>
                  {product.liga && <span className="tag">{product.liga}</span>}
                  {product.equipo && <span className="tag blue">{product.equipo}</span>}
                </div>
              )}
            </div>

            {/* Precio destacado */}
            <div className="price-hero">
              <span className="price-hero-value">desde {product.precio ?? 18}€</span>
              <span className="price-hero-note">IVA incluido · envío a toda España</span>
            </div>

            {/* Tabla de precios */}
            <div className="price-table">
              <p className="price-table-title">Opciones de personalización</p>
              <div className="price-row">
                <div>
                  <span className="price-row-label">Sin personalización</span>
                  <p className="price-row-sub">Camiseta tal cual, sin dorsal</p>
                </div>
                <span className="price-row-value highlighted">{product.precio ?? 18}€</span>
              </div>
              <div className="price-divider" />
              <div className="price-row">
                <div>
                  <span className="price-row-label">Nombre + número</span>
                  <p className="price-row-sub">Dorsal personalizado impreso</p>
                </div>
                <span className="price-row-value">21€</span>
              </div>
              <div className="price-divider" />
              <div className="price-row">
                <div>
                  <span className="price-row-label">Nombre + número + parches</span>
                  <p className="price-row-sub">Liga, Champions, Mundial…</p>
                </div>
                <span className="price-row-value">22€</span>
              </div>
            </div>

            {/* Tallas */}
            {tallas.length > 0 && (
              <div>
                <p className="modal-section-title">Tallas disponibles</p>
                <div className="tallas-grid">
                  {tallas.map(t => (
                    <span key={t} className="talla-chip">{t}</span>
                  ))}
                </div>
              </div>
            )}

            {/* Envío */}
            <div className="info-cards">
              <div className="info-card">
                <span className="info-card-icon">🚚</span>
                <div>
                  <p className="info-card-title">Envío a España</p>
                  <p className="info-card-text">10–15 días hábiles</p>
                </div>
              </div>
              <div className="info-card">
                <span className="info-card-icon">💳</span>
                <div>
                  <p className="info-card-title">Pago por PayPal</p>
                  <p className="info-card-text">Seguro y sencillo</p>
                </div>
              </div>
              <div className="info-card">
                <span className="info-card-icon">✏️</span>
                <div>
                  <p className="info-card-title">Personalización</p>
                  <p className="info-card-text">Dorsal a tu elección</p>
                </div>
              </div>
              <div className="info-card">
                <span className="info-card-icon">📦</span>
                <div>
                  <p className="info-card-title">Alta calidad</p>
                  <p className="info-card-text">Réplica premium</p>
                </div>
              </div>
            </div>

            {/* Yupoo */}
            {product.yupoo_url && (
              <a className="yupoo-link" href={product.yupoo_url} target="_blank" rel="noopener noreferrer">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                  <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                </svg>
                Ver en catálogo del proveedor
              </a>
            )}

            {/* CTA */}
            <a className="btn-telegram" href={tgLink} target="_blank" rel="noopener noreferrer">
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
