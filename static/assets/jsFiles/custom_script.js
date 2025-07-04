$(document).on('submit', 'form', function (e) {
    const $form = $(this);
    const $submitBtn = $form.find('button[type="submit"]:focus');

    if ($submitBtn.length) {
        $submitBtn
            .addClass('processing')
            .prop('disabled', true)
            .html('Processing... <i class="fas fa-spinner fa-spin ml-2 ms-2"></i>');
    }
});


$(document).on('click', 'a[href^="/"]:not([data-no-process])', function (e) {
    const $element = $(this);

    $element
        .addClass('processing')
        .html('Processing... <i class="fas fa-spinner fa-spin ml-2 ms-2"></i>');

    // Let the browser follow the link normally (no e.preventDefault)
});
