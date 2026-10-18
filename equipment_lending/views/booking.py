from datetime import date, timedelta
from html import escape


def render_booking_form(equipment):
    today = date.today()
    tomorrow = today + timedelta(days=1)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Book {escape(equipment.name)} · Community Lending</title>
<link rel="icon" href="data:,">
<style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #f5f7f6; color: #18352d; font: 16px/1.6 system-ui, sans-serif; }}
main {{ max-width: 720px; margin: auto; padding: 28px 20px; }}
a {{ color: #23614d; }}
h1 {{ line-height: 1.2; overflow-wrap: anywhere; }}
section {{ background: white; border: 1px solid #d7e2dc; border-radius: 12px; padding: 24px; margin-top: 24px; }}
label {{ display: grid; gap: 6px; margin: 16px 0; min-width: 0; font-weight: 600; }}
input, textarea, button {{ font: inherit; min-height: 46px; border-radius: 6px; padding: 10px 12px; }}
input, textarea {{ width: 100%; min-width: 0; border: 1px solid #879d93; background: white; color: #18352d; }}
button {{ background: #23614d; color: white; border: 0; cursor: pointer; }}
button:disabled {{ opacity: .6; cursor: default; }}
fieldset {{ border: 0; margin: 0; padding: 0; min-width: 0; }}
.dates {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
:focus-visible {{ outline: 3px solid #aa6a12; outline-offset: 3px; }}
[role="alert"] {{ color: #9c2020; white-space: pre-line; }}
[role="status"] {{ color: #195039; }}
@media (max-width: 600px) {{ .dates {{ grid-template-columns: 1fr; gap: 0; }} section {{ padding: 18px; }} button {{ width: 100%; }} }}
</style></head><body><main>
<a href="/">← Equipment catalogue</a>
<h1>Book {escape(equipment.name)}</h1>
<p>{escape(equipment.description)}</p>
<p>{escape(equipment.category)} · Collection: {escape(equipment.location)}</p>
<section id="login-panel">
<h2>Sign in to request this equipment</h2>
<form id="login-form">
<label>Email<input name="email" type="email" autocomplete="username" required></label>
<label>Password<input name="password" type="password" autocomplete="current-password" required></label>
<button type="submit">Sign in</button>
</form></section>
<p id="identity" role="status"></p>
<section><h2>Borrowing details</h2>
<form id="booking-form" data-equipment-id="{equipment.id}">
<fieldset id="booking-fields" disabled>
<div class="dates">
<label>Start date<input name="start_date" type="date" min="{today.isoformat()}" required></label>
<label>End date<input name="end_date" type="date" min="{tomorrow.isoformat()}" required></label>
</div>
<label>Purpose<textarea name="purpose" rows="4" maxlength="1000" required placeholder="Describe the activity and how the equipment will be used."></textarea></label>
<button type="submit">Submit request</button>
</fieldset></form>
<p id="result" role="status"></p></section>
<p id="error" role="alert"></p>
<noscript>JavaScript is required to sign in and submit a booking request.</noscript>
</main>""" + BOOKING_SCRIPT + "</body></html>"


BOOKING_SCRIPT = r"""
<script>
const loginForm = document.getElementById('login-form');
const bookingForm = document.getElementById('booking-form');
const fields = document.getElementById('booking-fields');
const error = document.getElementById('error');
const result = document.getElementById('result');
const start = bookingForm.elements.start_date;
const end = bookingForm.elements.end_date;
let token = '';

function showApiError(data) {
    error.textContent = Array.isArray(data.detail)
        ? data.detail.map(item => item.msg).join('\n')
        : data.detail;
}

loginForm.addEventListener('submit', async event => {
    event.preventDefault();
    error.textContent = '';
    const button = loginForm.querySelector('button');
    button.disabled = true;
    try {
        const response = await fetch('/auth/login', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email: loginForm.elements.email.value, password: loginForm.elements.password.value})
        });
        const data = await response.json();
        if (!response.ok) { showApiError(data); return; }
        token = data.access_token;
        loginForm.reset();
        document.getElementById('login-panel').hidden = true;
        document.getElementById('identity').textContent = 'Signed in as ' + data.user.name;
        fields.disabled = false;
        start.focus();
    } catch (failure) {
        console.error('Sign-in request failed', failure);
        error.textContent = 'Unable to sign in. Check your connection and try again.';
    } finally { button.disabled = false; }
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
            headers: {'Content-Type': 'application/json', Authorization: 'Bearer ' + token},
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
                token = '';
                fields.disabled = true;
                document.getElementById('identity').textContent = '';
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
</script>
"""
