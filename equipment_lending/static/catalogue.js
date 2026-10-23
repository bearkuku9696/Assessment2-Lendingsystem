const activeBookingStatuses = new Set(['pending', 'approved', 'borrowed']);

function showAdminBookingDetails(bookings) {
    const bookingsByEquipment = new Map();
    for (const booking of bookings) {
        if (!activeBookingStatuses.has(booking.status)) continue;
        const equipmentBookings = bookingsByEquipment.get(booking.equipment_id) || [];
        equipmentBookings.push(booking);
        bookingsByEquipment.set(booking.equipment_id, equipmentBookings);
    }

    for (const card of document.querySelectorAll('.card[data-equipment-id]')) {
        const equipmentBookings = bookingsByEquipment.get(Number(card.dataset.equipmentId));
        if (!equipmentBookings) continue;

        const details = card.querySelector('.admin-booking-details');
        const heading = document.createElement('h3');
        heading.textContent = 'Active booking details';
        const list = document.createElement('ul');
        for (const booking of equipmentBookings) {
            const item = document.createElement('li');
            item.textContent = 'Status: ' + booking.status + ' · Applicant: '
                + booking.applicant_name + ' (' + booking.applicant_email + ')';
            list.append(item);
        }
        details.replaceChildren(heading, list);
        details.hidden = false;
    }
}

window.sessionReady.then(async user => {
    if (!user || user.role !== 'admin') return;
    const response = await fetch('/admin/bookings', {
        headers: {Authorization: 'Bearer ' + sessionStorage.getItem('access_token')},
        cache: 'no-store'
    });
    if (!response.ok) throw new Error('Unable to load administrator booking details.');
    showAdminBookingDetails(await response.json());
}).catch(failure => {
    console.error('Administrator booking details failed', failure);
    document.getElementById('admin-booking-error').textContent = 'Unable to load administrator booking details.';
});
