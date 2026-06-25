// Logic to switch between Login and Onboarding forms
function switchForm(formType) {
    const loginSection = document.getElementById('login-section');
    const onboardSection = document.getElementById('onboard-section');
    const loginBtn = document.getElementById('nav-login-btn');
    const onboardBtn = document.getElementById('nav-onboard-btn');

    if (formType === 'login') {
        // Show Login, Hide Onboard
        loginSection.classList.remove('hidden');
        loginSection.classList.add('active');
        onboardSection.classList.remove('active');
        onboardSection.classList.add('hidden');

    } else if (formType === 'onboard') {
        // Show Onboard, Hide Login
        onboardSection.classList.remove('hidden');
        onboardSection.classList.add('active');
        loginSection.classList.remove('active');
        loginSection.classList.add('hidden');
    }
}

// Automatically fetch Address details based on Pincode using API
function fetchAddressData() {
    let pincode = document.getElementById('pincode').value;
    
    // Wait until pincode is 6 digits long
    if (pincode.length === 6) {
        fetch(`https://api.postalpincode.in/pincode/${pincode}`)
            .then(response => response.json())
            .then(data => {
                if (data[0].Status === "Success") {
                    let postOffice = data[0].PostOffice[0];
                    document.getElementById('state').value = postOffice.State;
                    document.getElementById('district').value = postOffice.District;
                    
                    // Automatically detect village/town using Block (Taluk) or Name as fallback
                    let detectedCity = (postOffice.Block && postOffice.Block !== "NA") ? postOffice.Block : postOffice.Name;
                    document.getElementById('village_or_city').value = detectedCity;
                    
                    document.getElementById('country').value = postOffice.Country;
                } else {
                    console.log("Invalid Pincode");
                }
            })
            .catch(error => console.error('Error fetching pincode data:', error));
    }
}

document.addEventListener("DOMContentLoaded", function() {
    const onboardForm = document.querySelector("#onboard-section form");
    if (onboardForm) {
        onboardForm.addEventListener("submit", function(event) {
            const password = onboardForm.querySelector("input[name='password']").value;
            // one special char, one num, one upper case, min 8 chars
            const passwordRegex = /^(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]).{8,}$/;
            if (!passwordRegex.test(password)) {
                event.preventDefault();
                alert("Password must contain at least 8 characters, one uppercase letter, one number, and one special character.");
            }
        });

        // Listen for input changes to unlock Complete button only when valid
        const inputs = onboardForm.querySelectorAll("input[required]");
        inputs.forEach(input => {
            input.addEventListener("input", checkFormValidity);
        });
    }
});

window.isOtpVerified = false;

function checkFormValidity() {
    const onboardForm = document.querySelector("#onboard-section form");
    const submitBtn = document.getElementById('complete-onboarding-btn');
    if (onboardForm && submitBtn) {
        // checkValidity() will be true if all 'required' fields have a value
        if (onboardForm.checkValidity() && window.isOtpVerified) {
            submitBtn.disabled = false;
            submitBtn.style.opacity = '1';
            submitBtn.style.cursor = 'pointer';
        } else {
            submitBtn.disabled = true;
            submitBtn.style.opacity = '0.5';
            submitBtn.style.cursor = 'not-allowed';
        }
    }
}

// Send OTP via AJAX
let otpResendTimer;

function sendOTP() {
    const emailInput = document.getElementById('company_email');
    const email = emailInput.value.trim();
    const messageEl = document.getElementById('otp-message');
    
    if (!email) {
        alert("Please enter a valid company email first.");
        return;
    }
    
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    // Disable button to prevent spamming
    const sendBtn = document.getElementById('send-otp-btn');
    sendBtn.disabled = true;
    sendBtn.innerText = "Sending...";
    
    fetch('/onboard/send-otp/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrfToken
        },
        body: new URLSearchParams({
            'email': email
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            document.getElementById('otp-group').style.display = 'block';
            document.getElementById('otp-group').classList.remove('hidden');
            messageEl.innerText = data.message;
            messageEl.style.color = 'var(--primary-color, green)';
            
            // Start 60-second countdown before allowing resend
            let timeLeft = 60;
            sendBtn.disabled = true;
            sendBtn.innerText = `Resend OTP (${timeLeft}s)`;
            
            clearInterval(otpResendTimer);
            otpResendTimer = setInterval(() => {
                timeLeft--;
                if (timeLeft <= 0) {
                    clearInterval(otpResendTimer);
                    sendBtn.disabled = false;
                    sendBtn.innerText = "Resend OTP";
                } else {
                    sendBtn.innerText = `Resend OTP (${timeLeft}s)`;
                }
            }, 1000);
            
        } else {
            alert(data.message);
            sendBtn.disabled = false;
            sendBtn.innerText = "Send OTP";
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert("An error occurred while sending OTP.");
        sendBtn.disabled = false;
        sendBtn.innerText = "Send OTP";
    });
}

// Verify OTP via AJAX
function verifyOTP() {
    const emailInput = document.getElementById('company_email');
    const email = emailInput.value.trim();
    const otpInput = document.getElementById('otp_input');
    const otp = otpInput.value.trim();
    const messageEl = document.getElementById('otp-message');
    
    if (!email || !otp) {
        alert("Please enter both email and OTP.");
        return;
    }
    
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    const verifyBtn = document.getElementById('verify-otp-btn');
    verifyBtn.disabled = true;
    verifyBtn.innerText = "Verifying...";
    
    fetch('/onboard/verify-otp/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrfToken
        },
        body: new URLSearchParams({
            'email': email,
            'otp': otp
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            messageEl.innerText = data.message;
            messageEl.style.color = 'var(--primary-color, green)';
            verifyBtn.innerText = "Verified";
            
            window.isOtpVerified = true;
            checkFormValidity();
            
            // Lock the email input so they can't change it after verifying
            emailInput.readOnly = true;
            otpInput.readOnly = true;
        } else {
            messageEl.innerText = data.message;
            messageEl.style.color = 'red';
            verifyBtn.disabled = false;
            verifyBtn.innerText = "Verify OTP";
        }
    })
    .catch(error => {
        console.error('Error:', error);
        messageEl.innerText = "An error occurred while verifying OTP.";
        messageEl.style.color = 'red';
        verifyBtn.disabled = false;
        verifyBtn.innerText = "Verify OTP";
    });
}