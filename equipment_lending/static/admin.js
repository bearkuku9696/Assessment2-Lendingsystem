const reviewRows = document.getElementById('review-bookings');
const reviewTable = document.getElementById('review-table');
const reviewAccess = document.getElementById('review-access');
const reviewError = document.getElementById('review-error');
const refreshBookings = document.getElementById('refresh-bookings');
let activeOperations = 0;
let loadingReservations = false;

function requireAdminLogin() {
    sessionStorage.removeItem('access_token');
    reviewRows.replaceChildren();
    reviewTable.hidden = true;
    refreshBookings.hidden = true;
    document.getElementById('session-name').textContent = '';
    document.getElementById('sign-out').hidden = true;
    document.getElementById('admin-link').hidden = true;
    document.getElementById('my-bookings-link').hidden = true;
    document.getElementById('sign-in-link').hidden = false;
    document.getElementById('register-link').hidden = false;
    reviewAccess.textContent = 'Your session has expired. Sign in again to review reservations.';
}

function apiMessage(data) {
    return Array.isArray(data.detail) ? data.detail.map(item => item.msg).join('\n') : data.detail;
}

function bookingRow(booking) {
    const row = document.createElement('tr');
    for (const value of [booking.id, booking.applicant_name, booking.applicant_email,
        booking.equipment_name, booking.start_date + ' – ' + booking.end_date,
        booking.purpose, booking.status + (booking.is_overdue ? ' — Overdue' : '')]) {
        const cell = document.createElement('td');
        cell.textContent = value;
        row.append(cell);
    }
    if (booking.is_overdue) row.classList.add('overdue-row');
    const times = document.createElement('td');
    times.className = 'actual-times';
    times.textContent = 'Picked up: ' + (booking.picked_up_at ? new Date(booking.picked_up_at).toLocaleString() : '—')
        + '\nReturned: ' + (booking.returned_at ? new Date(booking.returned_at).toLocaleString() : '—');
    row.append(times);
    const reviewCell = document.createElement('td');
    reviewCell.className = 'review-cell';
    row.append(reviewCell);
    const availableActions = {pending: ['approve', 'reject'], approved: ['pickup'], borrowed: ['return']}[booking.status] || [];
    if (!availableActions.length) {
        reviewCell.textContent = booking.admin_notes || '—';
        return row;
    }
    const form = document.createElement('form');
    const fields = document.createElement('fieldset');
    const label = document.createElement('label');
    label.textContent = 'Admin notes / rejection reason';
    const notes = document.createElement('textarea');
    notes.name = 'admin_notes';
    notes.maxLength = 2000;
    notes.rows = 3;
    notes.value = booking.admin_notes;
    if (booking.status === 'pending') {
        label.append(notes);
        fields.append(label);
    } else {
        const savedNotes = document.createElement('p');
        savedNotes.textContent = booking.admin_notes || 'No admin notes.';
        fields.append(savedNotes);
    }
    const actions = document.createElement('div');
    actions.className = 'review-actions';
    for (const action of availableActions) {
        const button = document.createElement('button');
        button.type = 'submit';
        button.dataset.action = action;
        button.textContent = {approve: 'Approve', reject: 'Reject', pickup: 'Confirm pickup', return: 'Confirm return'}[action];
        if (action === 'reject') button.className = 'reject-button';
        actions.append(button);
    }
    fields.append(actions);
    const message = document.createElement('p');
    message.setAttribute('role', 'alert');
    form.append(fields, message);
    reviewCell.append(form);
    form.addEventListener('submit', async event => {
        event.preventDefault();
        const action = event.submitter?.dataset.action;
        if (!action || fields.disabled || loadingReservations) return;
        message.textContent = '';
        if (action === 'reject' && !notes.value.trim()) {
            message.textContent = 'Enter a reason before rejecting this reservation.';
            notes.focus();
            return;
        }
        fields.disabled = true;
        activeOperations += 1;
        refreshBookings.disabled = true;
        try {
            const response = await fetch('/admin/bookings/' + booking.id + '/' + action, {
                method: 'POST',
                headers: {'Content-Type': 'application/json',
                    Authorization: 'Bearer ' + sessionStorage.getItem('access_token')},
                body: JSON.stringify(booking.status === 'pending' ? {admin_notes: notes.value} : {})
            });
            if (response.status === 401) { requireAdminLogin(); return; }
            const data = await response.json();
            if (!response.ok) { message.textContent = apiMessage(data); return; }
            row.replaceWith(bookingRow(data));
            reviewAccess.textContent = 'Reservation #' + booking.id + ' ' + data.status + '.';
        } catch (failure) {
            console.error('Reservation operation failed', failure);
            message.textContent = 'The result could not be confirmed. Refresh reservations before trying again.';
        } finally {
            fields.disabled = false;
            activeOperations -= 1;
            refreshBookings.disabled = activeOperations > 0 || loadingReservations;
        }
    });
    return row;
}

async function loadBookings() {
    if (activeOperations || loadingReservations) return;
    loadingReservations = true;
    refreshBookings.disabled = true;
    for (const fields of reviewRows.querySelectorAll('fieldset')) fields.disabled = true;
    reviewError.textContent = '';
    try {
        const response = await fetch('/admin/bookings', {
            headers: {Authorization: 'Bearer ' + sessionStorage.getItem('access_token')}, cache: 'no-store'
        });
        if (response.status === 401) { requireAdminLogin(); return; }
        const data = await response.json();
        if (!response.ok) throw new Error(apiMessage(data));
        reviewRows.replaceChildren(...data.map(bookingRow));
        document.getElementById('actual-times-heading').textContent = 'Actual times (local)';
        reviewTable.hidden = false;
        refreshBookings.hidden = false;
        reviewAccess.textContent = data.length ? 'Review requests, confirm pickup or return. Actual times are shown in your local timezone.'
            : 'No reservations have been submitted.';
    } catch (failure) {
        reviewError.textContent = failure.message || 'Unable to load reservations. Please refresh to try again.';
    } finally {
        loadingReservations = false;
        refreshBookings.disabled = false;
        for (const fields of reviewRows.querySelectorAll('fieldset')) fields.disabled = false;
    }
}

refreshBookings.addEventListener('click', loadBookings);
window.sessionReady.then(async user => {
    if (!user || user.role !== 'admin') {
        reviewRows.replaceChildren();
        reviewTable.hidden = true;
        reviewAccess.textContent = user ? 'Administrator access is required.'
            : 'Sign in with an administrator account to review reservations.';
        return;
    }
    refreshBookings.hidden = false;
    await loadBookings();
}).catch(() => { reviewError.textContent = 'Unable to verify your session. Reload to try again.'; });
