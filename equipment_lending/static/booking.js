const bookingForm = document.getElementById('booking-form');
const fields = document.getElementById('booking-fields');
const error = document.getElementById('error');
const result = document.getElementById('result');
const start = bookingForm.elements.start_date;
const end = bookingForm.elements.end_date;

function showApiError(data) {
    error.textContent = Array.isArray(data.detail)
        ? data.detail.map(item => item.msg).join('\n')
        : data.detail;
}

window.sessionReady.then(user => {
    if (user) {
        document.getElementById('login-panel').hidden = true;
        fields.disabled = false;
    }
}).catch(failure => {
    console.error('Booking authentication failed', failure);
    error.textContent = 'Unable to verify your session. Reload to try again.';
});

start.addEventListener('change', () => {
    if (start.value) {
        const nextDay = new Date(start.value + 'T00:00:00Z');
        nextDay.setUTCDate(nextDay.getUTCDate() + 1);
        end.min = nextDay.toISOString().slice(0, 10);
    }
});

bookingForm.addEventListener('submit', async event => {
    event.preventDefault();
    error.textContent = '';
    const button = bookingForm.querySelector('button');
    button.disabled = true;
    try {
        const response = await fetch('/bookings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', Authorization: 'Bearer ' + sessionStorage.getItem('access_token')},
            body: JSON.stringify({
                equipment_id: Number(bookingForm.dataset.equipmentId),
                start_date: start.value, end_date: end.value,
                purpose: bookingForm.elements.purpose.value
            })
        });
        const data = await response.json();
        if (!response.ok) {
            showApiError(data);
            if (response.status === 401) {
                sessionStorage.removeItem('access_token');
                fields.disabled = true;
                document.getElementById('identity').textContent = '';
                document.getElementById('session-name').textContent = '';
                document.getElementById('sign-out').hidden = true;
                document.getElementById('sign-in-link').hidden = false;
                document.getElementById('register-link').hidden = false;
                document.getElementById('login-panel').hidden = false;
            }
            return;
        }
        fields.disabled = true;
        result.textContent = 'Booking request #' + data.id + ' submitted for staff review. Status: ' + data.status + '.';
    } catch (failure) {
        console.error('Booking request failed', failure);
        error.textContent = 'The booking result could not be confirmed. Check your bookings before submitting again.';
    } finally { button.disabled = false; }
});
