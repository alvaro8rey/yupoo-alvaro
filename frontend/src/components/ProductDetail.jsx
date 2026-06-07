import React, { useState, useEffect, useCallback } from 'react';

const PRECIO_BASE            = 18;
const PRECIO_DORSAL          = 21;
const PRECIO_SOLO_PARCHES    = 20;
const PRECIO_PARCHES_COMPLETO = 24;

const PERS_OPTIONS = [
  { key: 'sin_personalizacion',      label: 'Sin personalización',        sub: 'Camiseta tal cual',                       precio: (base) => base },
  { key: 'nombre_numero',            label: 'Nombre + número',            sub: 'Dorsal personalizado impreso',            precio: () => PRECIO_DORSAL },
  { key: 'solo_parches',             label: 'Solo parches',               sub: 'Liga, Champions… sin dorsal',             precio: () => PRECIO_SOLO_PARCHES },
  { key: 'nombre_numero_parches',    label: 'Nombre + número + parches',  sub: 'Dorsal + Liga, Champions, Mundial…',      precio: () => PRECIO_PARCHES_COMPLETO },
];

export default function ProductDetail({ product, onClose, onAddToCart }) {
  const fotos  = product.fotos?.length ? product.fotos : (product.foto_path ? [product.foto_path] : []);
  const tallas = Array.isArray(product.tallas) ? product.tallas : [];

  const [activeIdx, setActiveIdx] = useState(0);
  const [imgError,  setImgError]  = useState({});
  const [lightbox,  setLightbox]  = useState(false);
  const [talla,     setTalla]     = useState(tallas[0] || '');
  const [pers,      setPers]      = useState('sin_personalizacion');
  const [added,     setAdded]     = useState(false);

  useEffect(() => {
    setActiveIdx(0); setImgError({}); setLightbox(false);
    setTalla(tallas[0] || ''); setPers('sin_personalizacion'); setAdded(false);
  }, [product.id]);

  const prev = useCallback(() => setActiveIdx(i => (i - 1 + fotos.length) % fotos.length), [fotos.length]);
  const next = useCallback(() => setActiveIdx(i => (i + 1) % fotos.length), [fotos.length]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'ArrowRight') next();
      else if (e.key === 'ArrowLeft') prev();
      else if (e.key === 'Escape') { if (lightbox) setLightbox(false); else onClose(); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [prev, next, lightbox, onClose]);

  const activePhoto  = fotos[activeIdx] || null;
  const refLabel     = `#${String(product.id).padStart(4, '0')}`;
  const handleImgError = (src) => setImgError(prev => ({ ...prev, [src]: true }));
  const precioActual = PERS_OPTIONS.find(o => o.key === pers)?.precio(product.precio ?? PRECIO_BASE) ?? (product.precio ?? PRECIO_BASE);

  const handleAddToCart = () => {
    if (!talla) return;
    onAddToCart({
      cartId:          Date.now() + Math.random(),
      producto_id:     product.id,
      nombre:          product.nombre,
      talla,
      personalizacion: pers,
      precio:          precioActual,
      portada_url:     fotos[0] || '',
    });
    setAdded(true);
    setTimeout(() => setAdded(false), 2000);
  };

  return (
    <>
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
              <div className="gallery-main-img" onClick={() => fotos.length && setLightbox(true)}
                style={{ cursor: fotos.length ? 'zoom-in' : 'default' }}>
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
              </div>
              {fotos.length > 1 && (
                <>
                  <div className="gallery-thumbs">
                    {fotos.map((foto, i) => (
                      <button key={i} className={`thumb-btn${activeIdx === i ? ' active' : ''}`}
                        onClick={() => setActiveIdx(i)} aria-label={`Foto ${i + 1}`}>
                        {!imgError[foto]
                          ? <img src={foto} alt={`Foto ${i+1}`} onError={() => handleImgError(foto)} />
                          : <div style={{width:'100%',height:'100%',background:'var(--gray-200)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:'.65rem',color:'var(--gray-400)'}}>{i+1}</div>
                        }
                      </button>
                    ))}
                  </div>
                  <p className="gallery-count">{activeIdx + 1} / {fotos.length}</p>
                </>
              )}
            </div>

            {/* ── Info ── */}
            <div className="modal-info">
              <div>
                <p className="modal-ref">{refLabel}</p>
                <h2 className="modal-name">{product.nombre}</h2>
                {(product.liga || product.equipo) && (
                  <div className="modal-tags" style={{marginTop:'.6rem'}}>
                    {product.liga   && <span className="tag">{product.liga}</span>}
                    {product.equipo && <span className="tag blue">{product.equipo}</span>}
                  </div>
                )}
              </div>

              {/* Precio dinámico */}
              <div className="price-hero">
                <span className="price-hero-value">{precioActual}€</span>
                <span className="price-hero-note">IVA incluido · envío a toda España</span>
              </div>

              {/* Selector de talla */}
              {tallas.length > 0 && (
                <div className="selector-section">
                  <p className="selector-label">Talla <span style={{color:'#e53e3e'}}>*</span></p>
                  <div className="talla-pills">
                    {tallas.map(t => (
                      <button key={t} className={`talla-pill${talla === t ? ' active' : ''}`}
                        onClick={() => setTalla(t)}>{t}</button>
                    ))}
                  </div>
                </div>
              )}

              {/* Selector de personalización */}
              <div className="selector-section">
                <p className="selector-label">Personalización</p>
                <div className="pers-options">
                  {PERS_OPTIONS.map(o => (
                    <button key={o.key} className={`pers-option${pers === o.key ? ' active' : ''}`}
                      onClick={() => setPers(o.key)}>
                      <span className="pers-option-check">
                        {pers === o.key && (
                          <svg viewBox="0 0 12 12" width="10" height="10">
                            <polyline points="1,6 4,9 11,2" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                        )}
                      </span>
                      <span className="pers-option-body">
                        <span className="pers-option-label">{o.label}</span>
                        <span className="pers-option-sub">{o.sub}</span>
                      </span>
                      <span className="pers-option-price">{o.precio(product.precio ?? PRECIO_BASE)}€</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Info cards */}
              <div className="info-cards">
                <div className="info-card"><span className="info-card-icon">🚚</span>
                  <div><p className="info-card-title">Envío España</p><p className="info-card-text">10–15 días hábiles</p></div>
                </div>
                <div className="info-card"><span className="info-card-icon">💳</span>
                  <div><p className="info-card-title">PayPal / Bizum</p><p className="info-card-text">Pago seguro</p></div>
                </div>
                <div className="info-card"><span className="info-card-icon">📦</span>
                  <div><p className="info-card-title">Alta calidad</p><p className="info-card-text">Réplica premium</p></div>
                </div>
                <div className="info-card"><span className="info-card-icon">✏️</span>
                  <div><p className="info-card-title">Personalización</p><p className="info-card-text">Dorsal a tu elección</p></div>
                </div>
              </div>

              {/* Botón añadir al carrito */}
              <button
                className={`btn-add-cart${added ? ' added' : ''}${!talla ? ' disabled' : ''}`}
                onClick={handleAddToCart}
                disabled={!talla}
              >
                {added ? (
                  <>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" width="18" height="18">
                      <polyline points="20 6 9 17 4 12"/>
                    </svg>
                    ¡Añadido al carrito!
                  </>
                ) : (
                  <>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="18" height="18">
                      <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
                      <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
                    </svg>
                    {!talla ? 'Elige una talla' : 'Añadir al carrito'}
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ── Lightbox ── */}
      {lightbox && (
        <div className="lightbox-overlay" onClick={() => setLightbox(false)}>
          <button className="lightbox-close" onClick={() => setLightbox(false)} aria-label="Cerrar">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
          {fotos.length > 1 && (
            <button className="lightbox-arrow left" onClick={e => { e.stopPropagation(); prev(); }} aria-label="Anterior">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <polyline points="15 18 9 12 15 6"/>
              </svg>
            </button>
          )}
          <img className="lightbox-img" src={activePhoto} alt={product.nombre} onClick={e => e.stopPropagation()} />
          {fotos.length > 1 && (
            <button className="lightbox-arrow right" onClick={e => { e.stopPropagation(); next(); }} aria-label="Siguiente">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <polyline points="9 18 15 12 9 6"/>
              </svg>
            </button>
          )}
          {fotos.length > 1 && <p className="lightbox-counter">{activeIdx + 1} / {fotos.length}</p>}
        </div>
      )}
    </>
  );
}
