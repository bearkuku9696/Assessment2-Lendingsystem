const reviewRows = document.getElementById('review-bookings');
const reviewTable = document.getElementById('review-table');
const reviewAccess = document.getElementById('review-access');
const reviewError = document.getElementById('review-error');
const refreshBookings = document.getElementById('refresh-bookings');

function requireAdminLogin() {
    sessionStorage.removeItem('access_token');
    reviewRows.replaceChildren();
    reviewTable.hidden = true;
    refreshBookings.hidden = true;
    document.getElementById('session-name').textContent = '';
    document.getElementById('sign-out').hidden = true;
    document.getElementById('admin-link').hidden = true;
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
        booking.purpose, booking.status]) {
        const cell = document.createElement('td');
        cell.textContent = value;
        row.append(cell);
    }
    const reviewCell = document.createElement('td');
    reviewCell.className = 'review-cell';
    row.append(reviewCell);
    if (booking.status !== 'pending') {
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
    label.append(notes);
    fields.append(label);
    const actions = document.createElement('div');
    actions.className = 'review-actions';
    for (const action of ['approve', 'reject']) {
        const button = document.createElement('button');
        button.type = 'submit';
        button.dataset.action = action;
        button.textContent = action === 'approve' ? 'Approve' : 'Reject';
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
        if (!action || fields.disabled) return;
        message.textContent = '';
        if (action === 'reject' && !notes.value.trim()) {
            message.textContent = 'Enter a reason before rejecting this reservation.';
            notes.focus();
            return;
        }
        fields.disabled = true;
        try {
            const response = await fetch('/admin/bookings/' + booking.id + '/' + action, {
                method: 'POST',
                headers: {'Content-Type': 'application/json',
                    Authorization: 'Bearer ' + sessionStorage.getItem('access_token')},
                body: JSON.stringify({admin_notes: notes.value})
            });
            if (response.status === 401) { requireAdminLogin(); return; }
            const data = await response.json();
            if (!response.ok) { message.textContent = apiMessage(data); return; }
            row.replaceWith(bookingRow(data));
            reviewAccess.textContent = 'Reservation #' + booking.id + ' ' + data.status + '.';
        } catch (failure) {
            console.error('Reservation review failed', failure);
            message.textContent = 'The result could not be confirmed. Refresh reservations before trying again.';
        } finally { fields.disabled = false; }
    });
    return row;
}

async function loadBookings() {
    refreshBookings.disabled = true;
    reviewError.textContent = '';
    try {
        const response = await fetch('/admin/bookings', {
            headers: {Authorization: 'Bearer ' + sessionStorage.getItem('access_token')}, cache: 'no-store'
        });
        if (response.status === 401) { requireAdminLogin(); return; }
        const data = await response.json();
        if (!response.ok) throw new Error(apiMessage(data));
        reviewRows.replaceChildren(...data.map(bookingRow));
        reviewTable.hidden = false;
        refreshBookings.hidden = false;
        reviewAccess.textContent = data.length ? 'Review pending reservations below. Rejection requires a reason.'
            : 'No reservations have been submitted.';
    } catch (failure) {
        reviewError.textContent = failure.message || 'Unable to load reservations. Please refresh to try again.';
    } finally { refreshBookings.disabled = false; }
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
