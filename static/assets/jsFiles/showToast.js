function showToast(message, duration = 5000, options = {}) {

    // Create or use existing toast container
    let toastContainer = document.querySelector('.toast-container.position-fixed.bottom-0.end-0');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        toastContainer.style.zIndex = '1000002';
        document.body.appendChild(toastContainer);
    }

    // Create toast element
    const toast = document.createElement('div');
    toast.id = 'liveToast';
    toast.className = 'toast';
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');

    // Create toast header
    const toastHeader = document.createElement('div');
    toastHeader.className = 'toast-header';
    const icon = document.createElement('i');
    icon.className = 'fa-solid fa-comment me-1';
    //icon.src = options.image || 'https://via.placeholder.com/20'; // Default placeholder image
    //icon.alt = options.imageAlt || 'Icon';
    const title = document.createElement('strong');
    title.className = 'me-auto';
    title.textContent = options.title || 'Notification';
    const time = document.createElement('small');
    time.textContent = options.time || 'Just now';
    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'btn-close';
    closeBtn.setAttribute('data-bs-dismiss', 'toast');
    closeBtn.setAttribute('aria-label', 'Close');
    toastHeader.appendChild(icon);
    toastHeader.appendChild(title);
    toastHeader.appendChild(time);
    toastHeader.appendChild(closeBtn);

    // Create toast body
    const toastBody = document.createElement('div');
    toastBody.className = 'toast-body';
    toastBody.textContent = message;

    // Assemble toast
    toast.appendChild(toastHeader);
    toast.appendChild(toastBody);
    toastContainer.appendChild(toast);

    // Initialize and show toast
    const bsToast = new bootstrap.Toast(toast, { delay: duration });
    bsToast.show();

    // Remove toast when closed
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

// Example: Trigger toast on button click
document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('liveToastBtn');
    if (btn) {
        btn.addEventListener('click', () => {
            showToast('Hello, world! This is a toast message.', 5000, {
                title: 'Bootstrap',
                time: '11 mins ago',
                image: 'https://via.placeholder.com/20' // Replace with actual image URL
            });
        });
    }
});