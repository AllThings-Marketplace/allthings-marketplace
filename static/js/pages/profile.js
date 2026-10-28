// static/js/pages/profile.js
document.addEventListener("DOMContentLoaded", function () {

    // === 1. Toggle Collapsible "+ Add Address" Form ===
    const toggleAddressBtn = document.getElementById("toggleNewAddressBtn");
    const newAddressForm = document.getElementById("newAddressFormBox");

    if (toggleAddressBtn && newAddressForm) {
        toggleAddressBtn.addEventListener("click", function (e) {
            e.preventDefault();

            const isHidden =
                newAddressForm.classList.contains("hidden-initial") ||
                newAddressForm.style.display === "none" ||
                window.getComputedStyle(newAddressForm).display === "none";

            if (isHidden) {
                newAddressForm.classList.remove("hidden-initial");
                newAddressForm.style.display = "block";
                toggleAddressBtn.innerHTML = '<i class="fa-solid fa-xmark"></i> Cancel';
                toggleAddressBtn.classList.replace("btn-outline", "btn-secondary");

                const firstInput = newAddressForm.querySelector('input[name="label"]');
                if (firstInput) firstInput.focus();
            } else {
                newAddressForm.classList.add("hidden-initial");
                newAddressForm.style.display = "none";
                toggleAddressBtn.innerHTML = '<i class="fa-solid fa-plus"></i> Add Address';
                toggleAddressBtn.classList.replace("btn-secondary", "btn-outline");
            }
        });
    }

    // === 2. Inline Pencil Editing for Personal Details Form ===
    const formFields = document.querySelectorAll(
        '.profile-form-wrapper input:not([type="hidden"]):not([type="password"]), .profile-form-wrapper textarea'
    );

    formFields.forEach(field => {
        // Lock field initially
        field.setAttribute("readonly", true);
        field.classList.add("locked-field");

        // Wrap field for absolute positioning
        const wrapper = document.createElement("div");
        wrapper.className = "input-wrapper";

        field.parentNode.insertBefore(wrapper, field);
        wrapper.appendChild(field);

        // Create and inject pencil icon
        const pencil = document.createElement("i");
        pencil.className = "fa-solid fa-pencil edit-pencil";

        // Handle unlock interaction
        pencil.addEventListener("click", function () {
            field.removeAttribute("readonly");
            field.classList.remove("locked-field");
            field.focus();
            pencil.classList.add("active");
        });

        // Relock field if clicked away without changes
        field.addEventListener("blur", function () {
            if (field.value === field.defaultValue) {
                field.setAttribute("readonly", true);
                field.classList.add("locked-field");
                pencil.classList.remove("active");
            }
        });

        wrapper.appendChild(pencil);
    });
});