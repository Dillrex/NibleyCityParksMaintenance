document.addEventListener("DOMContentLoaded", () => {
    const container = document.getElementById("equipment-container");

    fetch("/api/equipment")
        .then(res => res.json())
        .then(data => {
            displayEquipment(data);
            document.getElementById("search-box").addEventListener("input", (e) => {
                const search = e.target.value.toLowerCase();
                const filtered = data.filter(eq => eq.name.toLowerCase().includes(search));
                displayEquipment(filtered);
            });
        });

    function displayEquipment(equipment) {
        container.innerHTML = "";
        equipment.forEach(eq => {
            const form = document.createElement("form");
            form.method = "POST";
            form.action = `/equipment/${eq.id}/update`;
            form.className = "card";
            form.innerHTML = `
                <strong>${eq.name} (${eq.type})</strong><br>
                <label>Status:</label>
                <select name="status">
                    <option ${eq.status === 'Working' ? 'selected' : ''}>Working</option>
                    <option ${eq.status === 'Broken' ? 'selected' : ''}>Broken</option>
                    <option ${eq.status === 'Needs oil change' ? 'selected' : ''}>Needs oil change</option>
                    <option ${eq.status === 'Custom' ? 'selected' : ''}>Custom</option>
                </select><br>
                <label>Interval:</label>
                <select name="oil_interval">
                    <option value="30" ${eq.oil_interval == 30 ? 'selected' : ''}>30d</option>
                    <option value="60" ${eq.oil_interval == 60 ? 'selected' : ''}>60d</option>
                    <option value="90" ${eq.oil_interval == 90 ? 'selected' : ''}>90d</option>
                    <option value="120" ${eq.oil_interval == 120 ? 'selected' : ''}>120d</option>
                </select><br>
                <small>Next: ${eq.next_oil_change} (${eq.days_remaining}d)</small><br>
                <button type="submit">Update</button>
            `;
            container.appendChild(form);
        });
    }

    fetch('/tickets/unread')
        .then(res => res.json())
        .then(data => {
            if (data.new_tickets) {
                const popup = document.createElement("div");
                popup.className = "alert-popup";
                popup.textContent = "📬 New ticket submitted!";
                document.body.appendChild(popup);
                setTimeout(() => popup.remove(), 5000);
            }
        });
});
