const form = document.getElementById('auth-form');
form.addEventListener('submit', async event => {
    event.preventDefault();
    const error = document.getElementById('error');
    const button = form.querySelector('button');
    error.textContent = '';
    button.disabled = true;
    try {
        const response = await fetch(form.dataset.action, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(Object.fromEntries(new FormData(form)))
        });
        const data = await response.json();
        if (!response.ok) {
            error.textContent = Array.isArray(data.detail)
                ? data.detail.map(item => item.msg).join('\n') : data.detail;
            return;
        }
        form.reset();
        if (form.dataset.action === '/auth/register') {
            window.location.assign('/login?' + new URLSearchParams({next: form.dataset.next, registered: 'true'}));
        } else {
            sessionStorage.setItem('access_token', data.access_token);
            window.location.assign(form.dataset.next);
        }
    } catch (failure) {
        console.error('Authentication request failed', failure);
        error.textContent = 'Unable to complete the request. Please check your connection and try again.';
    } finally { button.disabled = false; }
});
