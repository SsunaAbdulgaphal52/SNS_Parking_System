// JavaScript for the parking system.
// Part 1: ask "Are you sure?" before deleting a record.
// Part 2: on the ticket form, show the hours parked and an estimated fee.
// Part 3: on the Park a Car form, type the car plate in capital letters.
// Part 4: on the Make Payment page, show the amount as soon as a ticket is chosen.
// Part 5: on the receipt page, the Print button opens the print window.
// Part 6: load and submit forms in the Bootstrap modal.


// ---------- Part 1: confirm before delete ----------

// Select every delete form on the page
var deleteForms = document.querySelectorAll('.delete-form');

for (var i = 0; i < deleteForms.length; i++) {
    deleteForms[i].addEventListener('submit', function (event) {
        var sure = confirm('Are you sure you want to delete this record?');
        if (sure === false) {
            // stop the form from being sent
            event.preventDefault();
        }
    });
}


// ---------- Part 2: estimated parking fee on the ticket form ----------

// The parking rate: 1000 UGX per hour (same rate as RATE_PER_HOUR in models.py)
var RATE_PER_HOUR = 1000;

function showFee(form) {
    var entryInput = form.querySelector('#id_entry_time');
    var exitInput = form.querySelector('#id_exit_time');
    var feeBox = form.querySelector('#fee-box');

    if (entryInput === null || exitInput === null || feeBox === null) {
        return;
    }

    feeBox.style.display = 'block';
    if (entryInput.value === '' || exitInput.value === '') {
        feeBox.textContent = 'Enter the entry and exit time to see the estimated fee.';
        return;
    }

    var entry = new Date(entryInput.value);
    var exit = new Date(exitInput.value);

    // difference is in milliseconds, so divide to get hours
    var hours = (exit - entry) / (1000 * 60 * 60);

    if (hours <= 0) {
        feeBox.textContent = 'The exit time must be after the entry time.';
        return;
    }

    // round up: part of an hour counts as a full hour, minimum 1 hour
    var hoursToPay = Math.ceil(hours);
    if (hoursToPay < 1) {
        hoursToPay = 1;
    }
    var fee = hoursToPay * RATE_PER_HOUR;

    feeBox.textContent = 'Hours charged: ' + hoursToPay + ' | Estimated fee: UGX ' + fee;
}

document.addEventListener('change', function (event) {
    if (event.target.id === 'id_entry_time' || event.target.id === 'id_exit_time') {
        showFee(event.target.form);
    }
});

var ticketFormOnPage = document.querySelector('.data-form');
if (ticketFormOnPage !== null) {
    showFee(ticketFormOnPage);
}


// ---------- Part 3: capital letters for the car plate ----------

document.addEventListener('input', function (event) {
    if (event.target.id === 'id_car_plate') {
        event.target.value = event.target.value.toUpperCase();
    }
});


// ---------- Part 4: choose a ticket on the payment page ----------

document.addEventListener('change', function (event) {
    if (event.target.id === 'ticket-select' && event.target.value !== '') {
        // when a ticket is chosen, send the form so the page shows its amount
        event.target.form.requestSubmit();
    }
});


// ---------- Part 5: print button on the receipt ----------

// This button only exists on the receipt page
var printButton = document.getElementById('print-button');

if (printButton !== null) {
    printButton.addEventListener('click', function () {
        // opens the browser's print window
        window.print();
    });
}


// ---------- Part 6: forms in the shared Bootstrap modal ----------

var formModalElement = document.getElementById('form-modal');
var formModalBody = document.getElementById('form-modal-body');
var formModalTitle = document.getElementById('form-modal-title');
var formModal = formModalElement === null ? null : bootstrap.Modal.getOrCreateInstance(formModalElement);

function showModalError(message) {
    var error = document.createElement('p');
    error.className = 'modal-error';
    error.setAttribute('role', 'alert');
    error.textContent = message;
    formModalBody.prepend(error);
}

function renderModalPage(html, pageUrl) {
    var parsedPage = new DOMParser().parseFromString(html, 'text/html');
    var content = parsedPage.querySelector('#modal-page-content');

    if (content === null) {
        throw new Error('The requested page does not contain modal content.');
    }

    var heading = content.querySelector('h2');
    formModalTitle.textContent = heading === null ? 'Parking System' : heading.textContent.trim();
    if (heading !== null) {
        heading.remove();
    }

    var forms = content.querySelectorAll('form');
    for (var i = 0; i < forms.length; i++) {
        if (!forms[i].getAttribute('action')) {
            forms[i].setAttribute('action', pageUrl);
        }
    }
    formModalBody.innerHTML = content.innerHTML;

    var ticketFormInModal = formModalBody.querySelector('.data-form');
    if (ticketFormInModal !== null) {
        showFee(ticketFormInModal);
    }
}

function requestModalPage(url, options) {
    return fetch(url, options).then(function (response) {
        if (!response.ok) {
            throw new Error('The form could not be loaded or submitted. Please try again.');
        }
        return response.text().then(function (html) {
            // After a redirect: if the new page is also a pop-up page (check out
            // goes to the payment page) show it in the pop-up, else open the page
            if (response.redirected && html.indexOf('id="modal-page-content"') === -1) {
                window.location.assign(response.url);
                return;
            }
            renderModalPage(html, response.url);
        });
    });
}

if (formModal !== null) {
    document.addEventListener('click', function (event) {
        var trigger = event.target.closest('.js-modal-trigger');
        if (trigger !== null) {
            formModalBody.innerHTML = '<p>Loading...</p>';
            formModalTitle.textContent = 'Loading';
            try {
                formModal.show();
            } catch (error) {
                return;   // the pop-up could not open: the link opens as a normal page
            }
            event.preventDefault();

            requestModalPage(trigger.href, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            }).catch(function (error) {
                showModalError(error.message);
            });
            return;
        }

        if (event.target.closest('#form-modal .cancel-link') !== null) {
            event.preventDefault();
            formModal.hide();
        }
    });

    formModalBody.addEventListener('submit', function (event) {
        var form = event.target;
        if (form.tagName !== 'FORM') {
            return;
        }

        event.preventDefault();
        // Use getAttribute: the payment forms have a field called "method",
        // and form.method would give that field instead of "post"
        var method = (form.getAttribute('method') || 'get').toUpperCase();
        var url = new URL(form.getAttribute('action') || window.location.href, window.location.href);
        var options = {
            method: method,
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        };

        if (method === 'GET') {
            var query = new URLSearchParams(new FormData(form));
            url.search = query.toString();
        } else {
            options.body = new FormData(form);
        }

        requestModalPage(url.toString(), options).catch(function (error) {
            showModalError(error.message);
        });
    });
}
