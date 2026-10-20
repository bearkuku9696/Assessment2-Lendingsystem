async function loadSession() {
    const token = sessionStorage.getItem('access_token');
    if (!token) return null;
    const response = await fetch('/auth/me', {headers: {Authorization: 'Bearer ' + token}});
    if (response.status === 401) {
        sessionStorage.removeItem('access_token');
        return null;
    }
    if (!response.ok) throw new Error('Unable to verify your session.');
    const user = await response.json();
    document.getElementById('admin-link').hidden = user.role !== 'admin';
    document.getElementById('my-bookings-link').hidden = false;
    document.getElementById('sign-in-link').hidden = true;
    document.getElementById('register-link').hidden = true;
    document.getElementById('session-name').textContent = 'Signed in as ' + user.name;
    document.getElementById('sign-out').hidden = false;
    return user;
}
window.sessionReady = loadSession();
window.sessionReady.catch(failure => {
    console.error('Session check failed', failure);
    document.getElementById('session-error').textContent = 'Unable to verify your session. Reload to try again.';
});
document.getElementById('sign-out').addEventListener('click', async event => {
    event.target.disabled = true;
    try {
        const response = await fetch('/auth/logout', {
            method: 'POST', headers: {Authorization: 'Bearer ' + sessionStorage.getItem('access_token')}
        });
        if (!response.ok && response.status !== 401) throw new Error('Sign out failed.');
        sessionStorage.removeItem('access_token');
        window.location.reload();
    } catch (failure) {
        console.error('Sign out failed', failure);
        document.getElementById('session-error').textContent = 'Unable to sign out. Please try again.';
        event.target.disabled = false;
    }
});
