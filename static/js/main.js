document.addEventListener('DOMContentLoaded', () => {
  const cartBadge = document.querySelector('.bi-cart3').closest('a').querySelector('.badge');
  const subtotalEl = document.getElementById('cart-subtotal');
  const totalEl = document.getElementById('cart-total');
  const shipping = parseFloat(document.getElementById('cart-shipping').textContent.replace('$',''));

  function updateCart(productId, quantity) {
    fetch(`/update-cart/${productId}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({quantity: quantity})
    })
    .then(res => res.json())
    .then(data => {
      if(data.success){
        cartBadge.textContent = data.cart_quantity;
        document.querySelectorAll(`[data-id='${productId}'] .item-total`).forEach(el => {
          el.textContent = `$${data.item_total}`;
        });
        subtotalEl.textContent = `$${data.subtotal}`;
        totalEl.textContent = `$${data.subtotal + shipping}`;
      }
    });
  }

  function removeFromCart(productId) {
    fetch(`/remove-from-cart/${productId}`, { method: 'POST' })
    .then(res => res.json())
    .then(data => {
      if(data.success){
        cartBadge.textContent = data.cart_quantity;

        // Remove all matching product elements (table row & mobile card)
        document.querySelectorAll(`[data-id='${productId}']`).forEach(el => el.remove());

        subtotalEl.textContent = `$${data.subtotal}`;
        totalEl.textContent = `$${data.subtotal + shipping}`;

        // Show toast (optional)
        showToast('Product removed from cart', 'warning');
      }
    });
  }

  // Increase / Decrease / Quantity change
  document.querySelectorAll('.increase').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = document.querySelector(`.quantity[data-id='${btn.dataset.id}']`);
      input.value = parseInt(input.value)+1;
      updateCart(btn.dataset.id, parseInt(input.value));
    });
  });

  document.querySelectorAll('.decrease').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = document.querySelector(`.quantity[data-id='${btn.dataset.id}']`);
      if(parseInt(input.value) > 1){
        input.value = parseInt(input.value)-1;
        updateCart(btn.dataset.id, parseInt(input.value));
      }
    });
  });

  document.querySelectorAll('.quantity').forEach(input => {
    input.addEventListener('change', () => {
      let val = parseInt(input.value);
      if(val < 1) val = 1;
      input.value = val;
      updateCart(input.dataset.id, val);
    });
  });

  // Remove buttons
  document.querySelectorAll('.remove-item').forEach(btn => {
    btn.addEventListener('click', () => {
      removeFromCart(btn.dataset.id);
    });
  });

  // Toast helper (from your previous toast code)
  function showToast(message, category='info') {
    const toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) return;

    const existingToasts = toastContainer.querySelectorAll('.toast');
    if (existingToasts.length >= 2) existingToasts[0].remove();

    let bgClass = 'bg-primary text-white';
    if (category === 'success') bgClass = 'bg-success text-white';
    else if (category === 'danger') bgClass = 'bg-danger text-white';
    else if (category === 'warning') bgClass = 'bg-warning text-dark';
    else if (category === 'info') bgClass = 'bg-info text-dark';

    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center ${bgClass} border-0 mb-2 slide-in`;
    toastEl.setAttribute('role', 'alert');
    toastEl.setAttribute('aria-live', 'assertive');
    toastEl.setAttribute('aria-atomic', 'true');

    toastEl.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">${message}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    `;

    toastContainer.appendChild(toastEl);
    new bootstrap.Toast(toastEl, { delay: 3000, autohide: true }).show();
  }
});
