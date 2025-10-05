// Login page specific JavaScript
document.addEventListener("DOMContentLoaded", function() {
    // Initialize toast messages
    var toastElList = [].slice.call(document.querySelectorAll('.toast'));
    toastElList.forEach(function(toastEl) {
        var toast = new bootstrap.Toast(toastEl, { autohide: true, delay: 3000 });
        toast.show();
    });

    // Add any login-specific JavaScript here
    console.log('Login module loaded');
});