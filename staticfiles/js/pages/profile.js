// === Inline Editing for Profile Form ONLY ===
document.addEventListener("DOMContentLoaded", function() {
    // 1. Target ONLY the profile form, completely ignoring login/signup pages
    const formFields = document.querySelectorAll('.profile-form-wrapper input:not([type="hidden"]), .profile-form-wrapper textarea');

    // 2. If we are not on the profile page, stop running this script immediately
    if (formFields.length === 0) return;

    formFields.forEach(field => {
        // Lock field initially
        field.setAttribute('readonly', true);
        field.classList.add('locked-field');

        // Wrap field for absolute positioning
        const wrapper = document.createElement('div');
        wrapper.className = 'input-wrapper';
        
        field.parentNode.insertBefore(wrapper, field);
        wrapper.appendChild(field);

        // Create and inject pencil icon
        const pencil = document.createElement('i');
        pencil.className = 'fa-solid fa-pencil edit-pencil';

        // Handle unlock interaction
        pencil.addEventListener('click', function() {
            field.removeAttribute('readonly');
            field.classList.remove('locked-field');
            field.focus();
            pencil.classList.add('active');
        });

        // Relock field if clicked away without changes
        field.addEventListener('blur', function() {
            if (field.value === field.defaultValue) {
                field.setAttribute('readonly', true);
                field.classList.add('locked-field');
                pencil.classList.remove('active');
            }
        });

        wrapper.appendChild(pencil);
    });
});