// === Checkout Date Validation ===
document.addEventListener("DOMContentLoaded", function() {
    const scheduleInput = document.getElementById("scheduled_time");
    if (scheduleInput) {
        // Adjust for local timezone to ensure accurate cutoff
        const now = new Date();
        now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
        
        // Slices the ISO string to format YYYY-MM-DDTHH:MM perfectly for the input
        scheduleInput.min = now.toISOString().slice(0, 16);
    }
});