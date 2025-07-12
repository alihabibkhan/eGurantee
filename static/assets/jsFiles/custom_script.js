$(document).on('submit', 'form', function (e) {
    const $form = $(this);
    let $submitBtn = $form.find('button[type="submit"]:focus');

    // If no focused button (e.g. Enter key pressed), get the first submit button
    if (!$submitBtn.length) {
        $submitBtn = $form.find('button[type="submit"]').first();
    }

    if ($submitBtn.length) {
        $submitBtn
            .addClass('processing')
            .prop('disabled', true)
            .html('Processing... <i class="fas fa-spinner fa-spin ml-2 ms-2"></i>');
    }
});


$(document).on('click', 'a[href^="/"]:not([data-no-process]):not([class="breadcrumb-item"])', function (e) {
    const $element = $(this);

    $element
        .addClass('processing')
        .prop('disabled', true)
        .html('Processing... <i class="fas fa-spinner fa-spin ml-2 ms-2"></i>');

    // Let the browser follow the link normally (no e.preventDefault)
});
