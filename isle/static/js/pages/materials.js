$('trace-ul').delegate('.my-material-btn', 'click', (e) => {
    e.preventDefault();
    setOwnership(e.target);
});

if (isAssistant) {
    if (teamUpload && canUpload) {
        $('.confirm-material-btn').on('click', (e) => {
            e.preventDefault();
            confirmTeamUpload(e.target);
        });
    } else if (!eventUpload) {
        $('.transfer-material-btn').on('click', (e) => {
            e.preventDefault();
            const $obj = $(e.target);
            const data = {
                material_id: $obj.val(),
                type: 'event',
                from_user: fromUser,
            }
            $('#transfer-modal').data('material-id', $obj.val()).modal('show');
            transfer(
                $obj, 
                data,
                'Вы уверены, что хотите переместить этот файл в файлы мероприятия?',
                () => {
                    $obj.parents('li').remove();
                }
            );
        });
    }    
}

if (eventUpload) {
    $('.transfer-material-btn').on('click', (e) => {
        e.preventDefault();
        $('#transfer-modal').data('material-id', $(this).val()).modal('show');
    });
    $('.transfer-from-event').on('click', (e) => {
        e.preventDefault();
        const $obj = $(e.target);
        const data = {
            material_id: $('#transfer-modal').data('material-id'),
            dest_id: $obj.val(),
            type: $obj.data('type-to'),
        }
        transfer(
            $obj,
            data,
            'Вы уверены, что хотите переместить файл?',
            () => {
                const materialId = $('#transfer-modal').data('material-id');
                $(`.transfer-material-btn[value=${materialId}]`).parents('li').remove();
                $('#transfer-modal').modal('hide');
            }
        );
    });
    function get_html_for_edit_form(csrf, id, trace_id, select_options, is_summary, comment, can_edit_summary, summary_text, summary_id) {
        let textarea_input = '';
        if (is_summary && can_edit_summary)
            textarea_input = `<div><textarea name="summary" id="edit-summary-${summary_id}">${summary_text}</textarea></div>`;
        else if (!is_summary)
            textarea_input = `<textarea maxlength="255" name="comment" class="form-control full-width mb-6" placeholder="Описание файлов">${comment}</textarea>`;
        return `
            <form class="mt-20 change-event-material-form" method="post">
                <input type="hidden" name="csrfmiddlewaretoken" value="${csrf}">
                <input type="hidden" name="material_id" value="${id}">
                ${isAssistant ?
                `<select name="trace_name" class="material-type-select form-control mb-20">${select_options}</select>`
                :
                `<input type="hidden" name="trace_name" value="${trace_id}">`}
                ${textarea_input}
                <button class="btn btn-success save-edited-block">Сохранить</button>
                <button class="btn btn-danger cancel-block-edit">Отменить</button>
            </form>
        `;
    }
    $('body').delegate('.edit-event-block-material', 'click', (e) => {
        e.preventDefault();
        const $obj = $(e.target);
        const id = $obj.attr('value');
        const trace_id = $obj.parents('div.event-trace-materials-wrapper').data('trace-id');
        const comment = $obj.parents('li').data('comment') || '';
        const csrf = $('[name=csrfmiddlewaretoken]').val();
        let li = $obj.parents('li');
        let wrapper = li.find('div.info-string-edit');
        let select_options = '';
        let is_summary = !!$obj.data('is-summary');
        for (tid in tracesDict) {
            let name = tracesDict[tid];
            select_options += `<option value="${tid}"` + (tid == trace_id ? " selected": "") + `>${name}</option>`
        }
        can_edit_summary = $obj.data('can-edit');
        if (can_edit_summary) {
            $.ajax({
                method: 'GET',
                url: getFullSummaryUrl,
                data: {
                    id: $obj.data('file-id'),
                    type: $obj.data('type')
                },
                success: (data) => {
                    let html = get_html_for_edit_form(csrf, id, trace_id, select_options, is_summary, comment, can_edit_summary, data['text'], data['id']);
                    wrapper.html(html);
                    CKEDITOR.replace('edit-summary-' + data['id']);
                },
                error: () => {
                    let html = get_html_for_edit_form(csrf, id, trace_id, select_options, is_summary, comment, can_edit_summary);
                    wrapper.html(html);
                }
            })
        }
        else {
            let html = get_html_for_edit_form(csrf, id, trace_id, select_options, is_summary, comment, can_edit_summary);
            wrapper.html(html);
        }
        }).delegate('.cancel-block-edit', 'click', (e) => {
            e.preventDefault();
            let summary_input = $(e.target).parents('form').find('textarea[name=summary]')
            if (summary_input.length) {
                CKEDITOR.instances[summary_input.attr('id')].destroy();
            }
            $(e.target).parents('div.info-string-edit').html('');
        }).delegate('.save-edited-block', 'click', (e) => {
            e.preventDefault();
            const $obj = $(e.target);
            let summary_input = $obj.parents('form').find('textarea[name=summary]')
            if (summary_input.length) {
                summary_input.val(CKEDITOR.instances[summary_input.attr('id')].getData());
            }
            let data = $obj.parents('form').serializeArray();
            data.push({name: 'change_material_info', value: ''})
            $.post({
                url : '',
                method: 'POST',
                data: data,
                success: (data) => {
                    let wrapper = $('div.event-trace-materials-wrapper[data-trace-id=' + data.original_trace_id + ']').find('ul.list-group li[data-material-id=' + data.material_id + ']');
                    wrapper.find('div.info-string-edit').html('');
                    wrapper.data('comment', data.comment);
                    wrapper.find('.assistant-info-string').html(data.info_str);
                    if (summary_input.length) {
                        CKEDITOR.instances[summary_input.attr('id')].destroy();
                        wrapper.find('.summary-content-short').html(`
                            <strong>Конспект:</strong> ${data['summary']}
                        `);
                    }
                    if (data.trace_id != data.original_trace_id) {
                        let destination = $('div.event-trace-materials-wrapper[data-trace-id=' + data.trace_id + ']').find('ul.list-group');
                        wrapper.appendTo(destination);
                        show_trace_name(data.trace_id);
                        show_trace_name(data.original_trace_id);
                    }
                },
                error: () => {
                    // TODO show appropriate message
                    alert('error');
                }
            })
    });
}

$('.load-results-btn').on('click', (e) => {
    e.preventDefault();
    let div = $(e.target).parents('.material-result-div');
    div.find('form').removeClass('hidden');
    $(e.target).hide();
    $(e.target).parents('.material-result-div').find('.upload-circle-items-wrapper').show();
});

$('.hide-results-form-btn').on('click', (e) => {
    e.preventDefault();
    $(e.target).parents('.material-result-div').find('form').addClass('hidden');
    $(e.target).parents('.material-result-div').find('.load-results-btn').show();
    $(e.target).parents('.material-result-div').find('.upload-circle-items-wrapper').hide();
});

function setOwnership(obj) {
    const $obj = $(obj);
    const isOwner = $obj.attr('data-owner');
    $.ajax({
        url: $obj.data('url'),
        method: 'POST',
        data: {
            csrfmiddlewaretoken: csrfmiddlewaretoken,
            confirm: !isOwner,
        },
        success: (data) => {
            if (data.is_owner) {
                $obj.attr('data-owner', '').text('Это не мое').addClass('btn-danger').removeClass('btn-success');
            } else {
                $obj.removeAttr('data-owner').text('Это мое').addClass('btn-success').removeClass('btn-danger');
            }
            if (data.owners) {
                $obj.parents('li').find('.material-owners').html('Связан с: ' + data.owners);
            } else {
                $obj.parents('li').find('.material-owners').html('');
            }
        }
    });
}

function confirmTeamUpload(obj) {
    const $obj = $(obj);
    $.ajax({
        url: confirmTeamUploadUrl,
        method: 'POST',
        data: {
            material_id: $obj.val(),
            csrfmiddlewaretoken: csrfmiddlewaretoken,
        },
        success: () => {
            $obj.parents('li').addClass('confirmed-team-link');
            $obj.remove();
        },
        error: () => {
            // TODO show appropriate message
            alert('error');
        }
    });
}

function transfer($obj, data, msg, success) {
    if (confirm(msg)) {
        data['csrfmiddlewaretoken'] = csrfmiddlewaretoken;
        $.ajax({
            url: transferUrl,
            method: 'POST',
            data: data,
            success: success,
            error: () => {
                // TODO show appropriate message
                alert('error');
            }
        });
    }
}

$(document).ready(function() {
    $('body').delegate('.view-result-page', 'click', function(e) {
        e.preventDefault();
        if ($(this).data('url')) {
            window.location = $(this).data('url');
        }
    })
});
