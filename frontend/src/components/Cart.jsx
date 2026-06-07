import React from 'react';

const BOT_USERNAME = "camisetasgalbot";

const PERS_LABEL = {
  sin_personalizacion:   'Sin personalización',
  nombre_numero:         'Nombre + número',
  solo_parches:          'Solo parches',
  nombre_numero_parches: 'Nombre + número + parches',
};

function formatTelegramText(cart) {
  const lines = ['🛒 *Pedido desde la tienda*', ''];
  cart.forEach((item, i) => {
    lines.push(`*${i + 1}. ${item.nombre}*`);
    lines.push(`   • Talla: ${item.talla}`);
    lines.push(`   • ${PERS_LABEL[item.personalizacion]}`);
    if (item.nombre_dorsal || item.numero_dorsal) {
      lines.push(`   • Dorsal: ${item.nombre_dorsal} / ${item.numero_dorsal}`);
    }
    if (item.parches?.length) {
      lines.push(`   • Parches: ${item.parches.join(', ')}`);
    }
    lines.push(`   • Precio: ${item.precio}€`);
    lines.push('');
  });
  const total = cart.reduce((s, i) => s + i.precio, 0);
  lines.push(`💰 *Total estimado: ${total}€*`);
  lines.push('');
  lines.push('_(Envíame este mensaje para continuar con el pedido)_');
  return lines.join('\n');
}

export default function Cart({ cart, onRemove, onClose }) {
  const total = cart.reduce((s, i) => s + i.precio, 0);

  const handleCheckout = () => {
    if (!cart.length) return;
    const text = formatTelegramText(cart);
    const url  = `https://t.me/${BOT_USERNAME}?text=${encodeURIComponent(text)}`;
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  return (
    <>
      <div className="cart-overlay" onClick={onClose} />
      <aside className="cart-panel">
        <div className="cart-header">
          <h2 className="cart-title">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="20" height="20">
              <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
              <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
            </svg>
            Mi carrito
          </h2>
          <button className="cart-close" onClick={onClose} aria-label="Cerrar carrito">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" width="20" height="20">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        {cart.length === 0 ? (
          <div className="cart-empty">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" width="52" height="52" opacity=".3">
              <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
              <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
            </svg>
            <p>El carrito está vacío</p>
          </div>
        ) : (
          <>
            <ul className="cart-items">
              {cart.map(item => (
                <li key={item.cartId} className="cart-item">
                  {item.portada_url
                    ? <img src={item.portada_url} alt={item.nombre} className="cart-item-img" />
                    : <div className="cart-item-img cart-item-no-img">T</div>
                  }
                  <div className="cart-item-info">
                    <p className="cart-item-name">{item.nombre}</p>
                    <p className="cart-item-meta">Talla: <strong>{item.talla}</strong></p>
                    <p className="cart-item-meta">{PERS_LABEL[item.personalizacion]}</p>
                    {(item.nombre_dorsal || item.numero_dorsal) && (
                      <p className="cart-item-meta">👕 {item.nombre_dorsal} / {item.numero_dorsal}</p>
                    )}
                    {item.parches?.length > 0 && (
                      <p className="cart-item-meta">🏆 {item.parches.join(', ')}</p>
                    )}
                    <p className="cart-item-price">{item.precio}€</p>
                  </div>
                  <button className="cart-item-remove" onClick={() => onRemove(item.cartId)} aria-label="Eliminar">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" width="16" height="16">
                      <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                  </button>
                </li>
              ))}
            </ul>

            <div className="cart-footer">
              <div className="cart-total">
                <span>Total estimado</span>
                <span className="cart-total-price">{total}€</span>
              </div>
              <p className="cart-total-note">Precio final confirmado en Telegram · Envío incluido</p>
              <button className="btn-checkout" onClick={handleCheckout}>
                <svg viewBox="0 0 24 24" width="18" height="18">
                  <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12L7.17 13.954l-2.96-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.978.605z" fill="white"/>
                </svg>
                Finalizar compra en Telegram
              </button>
            </div>
          </>
        )}
      </aside>
    </>
  );
}
