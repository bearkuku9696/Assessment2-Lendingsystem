const memberBookings = document.getElementById('my-bookings-list');
const memberAccess = document.getElementById('bookings-access');
const memberError = document.getElementById('bookings-error');
const memberRefresh = document.getElementById('refresh-my-bookings');
let equipmentNames = new Map();
let activeCancellations = 0;
let loadingMemberBookings = false;

function memberLoginRequired() {
    sessionStorage.removeItem('access_token');
    memberBookings.replaceChildren();
    memberRefresh.hidden = true;
    document.getElementById('session-name').textContent = '';
    document.getElementById('sign-out').hidden = true;
    document.getElementById('admin-link').hidden = true;
    document.getElementById('my-bookings-link').hidden = true;
    document.getElementById('sign-in-link').hidden = false;
    document.getElementById('register-link').hidden = false;
    memberAccess.textContent = 'Your session has expired. Sign in again to view your reservations.';
}

function memberBookingCard(booking) {
    const card = document.createElement('article');
    card.className = 'panel reservation-card';
    if (booking.is_overdue) card.classList.add('overdue-row');
    const heading = document.createElement('h2');
    heading.textContent = '#' + booking.id + ' · ' + (equipmentNames.get(booking.equipment_id) || 'Equipment #' + booking.equipment_id);
    card.append(heading);
    for (const text of [
        'Borrowing period: ' + booking.start_date + ' – ' + booking.end_date,
        'Purpose: ' + booking.purpose,
        'Status: ' + booking.status + (booking.is_overdue ? ' — Overdue' : ''),
        'Actual pickup: ' + (booking.picked_up_at ? new Date(booking.picked_up_at).toLocaleString() : '—'),
        'Actual return: ' + (booking.returned_at ? new Date(booking.returned_at).toLocaleString() : '—')
    ]) {
        const paragraph = document.createElement('p');
        paragraph.textContent = text;
        card.append(paragraph);
    }
    if (!['pending', 'approved'].includes(booking.status)) return card;
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Cancel reservation';
    const message = document.createElement('p');
    message.setAttribute('role', 'alert');
    card.append(button, message);
    button.addEventListener('click', async () => {
        if (button.disabled || loadingMemberBookings) return;
        button.disabled = true;
        activeCancellations += 1;
        memberRefresh.disabled = true;
        message.textContent = '';
        try {
            const response = await fetch('/bookings/' + booking.id + '/cancel', {
                method: 'POST', headers: {Authorization: 'Bearer ' + sessionStorage.getItem('access_token')}
            });
            if (response.status === 401) { memberLoginRequired(); return; }
            const data = await response.json();
            if (!response.ok) { message.textContent = data.detail; return; }
            card.replaceWith(memberBookingCard(data));
            memberAccess.textContent = 'Reservation #' + booking.id + ' cancelled.';
        } catch (failure) {
            console.error('Cancellation failed', failure);
            message.textContent = 'The result could not be confirmed. Refresh reservations before trying again.';
        } finally {
            activeCancellations -= 1;
            button.disabled = false;
            memberRefresh.disabled = activeCancellations > 0 || loadingMemberBookings;
        }
    });
    return card;
}

async function loadMemberBookings() {
    if (activeCancellations || loadingMemberBookings) return;
    loadingMemberBookings = true;
    memberRefresh.disabled = true;
    memberError.textContent = '';
    for (const button of memberBookings.querySelectorAll('button')) button.disabled = true;
    try {
        const [response, equipment] = await Promise.all([
            fetch('/my-bookings', {headers: {Authorization: 'Bearer ' + sessionStorage.getItem('access_token')}, cache: 'no-store'}),
            fetch('/equipment').then(response => response.ok ? response.json() : []).catch(() => [])
        ]);
        if (response.status === 401) { memberLoginRequired(); return; }
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail);
        equipmentNames = new Map(equipment.map(item => [item.id, item.name]));
        memberBookings.replaceChildren(...data.map(memberBookingCard));
        memberAccess.textContent = data.length ? 'Pending or approved reservations can be cancelled. Actual times are shown in your local timezone.'
            : 'You have no reservations yet.';
    } catch (failure) {
        memberError.textContent = failure.message || 'Unable to load reservations. Please refresh to try again.';
    } finally {
        loadingMemberBookings = false;
        memberRefresh.disabled = false;
        for (const button of memberBookings.querySelectorAll('button')) button.disabled = false;
    }
}

memberRefresh.addEventListener('click', loadMemberBookings);
window.sessionReady.then(async user => {
    if (!user) return;
    memberRefresh.hidden = false;
    await loadMemberBookings();
}).catch(() => { memberError.textContent = 'Unable to verify your session. Reload to try again.'; });
