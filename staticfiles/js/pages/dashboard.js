document.addEventListener('DOMContentLoaded', function() {
    const bankSelect = document.getElementById('bankSelect');
    const bankNameInput = document.getElementById('bankNameInput');

    if (bankSelect && bankNameInput) {
        bankSelect.addEventListener('change', function() {
            const selectedOption = this.options[this.selectedIndex];
            bankNameInput.value = selectedOption.getAttribute('data-name');
        });
    }
});

// === Provider Location Capture ===
document.addEventListener("DOMContentLoaded", function() {
    const locationBtn = document.getElementById('getLocationBtn');
    const latInput = document.getElementById('latInput');
    const lonInput = document.getElementById('lonInput');

    if (locationBtn && latInput && lonInput) {
        locationBtn.addEventListener('click', function() {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    function(position) {
                        latInput.value = position.coords.latitude;
                        lonInput.value = position.coords.longitude;
                    },
                    function(error) {
                        alert("Error getting location. Please ensure location permissions are enabled for this site.");
                    },
                    { enableHighAccuracy: true }
                );
            } else {
                alert("Geolocation is not supported by your browser.");
            }
        });
    }
});