// Copyright (c) 2025, ahmadmohammad96 and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Export Customizations Module", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on('Export Customizations Module', {
    refresh: function(frm) {
        // Add custom fields if they don't exist
        if (!frm.meta.fields.find(f => f.fieldname === 'export_status')) {
            // These fields will be added via custom fields in doctype
            // We'll add them to the form here temporarily
            frm.add_custom_field({
                fieldname: 'export_status',
                fieldtype: 'Data',
                hidden: 1,
                label: 'Export Status'
            });
            
            frm.add_custom_field({
                fieldname: 'export_message',
                fieldtype: 'Data',
                hidden: 1,
                label: 'Export Message'
            });
            
            frm.add_custom_field({
                fieldname: 'last_export_update',
                fieldtype: 'Datetime',
                hidden: 1,
                label: 'Last Export Update'
            });
            
            frm.add_custom_field({
                fieldname: 'last_export_result',
                fieldtype: 'Code',
                hidden: 1,
                label: 'Last Export Result'
            });
        }
    
        // Add export button
        frm.add_custom_button(__('Export Customizations'), function() {
            // Check if form is saved
            if (frm.is_dirty()) {
                frappe.msgprint({
                    title: __('Save Required'),
                    indicator: 'red',
                    message: __('Please save the document before exporting customizations.')
                });
                return;
            }
            
            // Check if export is in progress
            if (frm.doc.export_status === 'In Progress') {
                frappe.msgprint({
                    title: __('Export In Progress'),
                    indicator: 'blue',
                    message: __('An export is already in progress. Please wait for it to complete.')
                });
                
                // Start polling for status
                frm.trigger('check_export_status');
                return;
            }
            
            // Confirm with user
            frappe.confirm(
                __('This will update hooks.py and export fixtures. The process might take some time and will run in the background. Do you want to continue?'),
                function() {
                    // User confirmed, proceed with export
                    frm.trigger('start_export');
                }
            );
        }).addClass('btn-primary');
        
        // Add help message
        if (!frm.doc.__islocal) {
            frm.set_intro(__(
                'Select the DocTypes, Client Scripts, and Server Scripts you want to export. ' +
                'The system will update fixtures in hooks.py and run the export fixtures command. ' +
                'Exported files will be stored as attachments to this document.'
            ), 'blue');
        }
        
        // Set validation for emails
        if (frm.fields_dict['emails'] && frm.fields_dict['emails'].grid) {
            if (frm.fields_dict['emails'].grid.get_field && frm.fields_dict['emails'].grid.get_field('email')) {
                frm.fields_dict['emails'].grid.get_field('email').get_query = function() {
                    return {
                        filters: {
                            'enable_incoming': 1
                        }
                    };
                };
            }
        }
        
        // Enhance UI for multi-select tables - safely check if fields exist
        ['export_doctypes', 'export_client_scripts', 'export_server_scripts'].forEach(function(field) {
            if (frm.fields_dict[field] && frm.fields_dict[field].grid) {
                frm.fields_dict[field].grid.cannot_add_rows = false;
                frm.fields_dict[field].grid.only_sortable = false;
            }
        });
        
        // Show export status if available
        if (frm.doc.export_status) {
            let indicator = 'blue';
            if (frm.doc.export_status === 'Completed') indicator = 'green';
            if (frm.doc.export_status === 'Failed') indicator = 'red';
            if (frm.doc.export_status === 'Completed with warnings') indicator = 'orange';
            
            frm.dashboard.add_indicator(
                `${__('Export')}: ${__(frm.doc.export_status)} - ${frm.doc.export_message || ''}`,
                indicator
            );
            
            // If status is 'In Progress', start checking for updates
            if (frm.doc.export_status === 'In Progress') {
                frm.trigger('check_export_status');
            }
        }
    },
    
    // Handle "all scripts" checkboxes
    all_client_scripts: function(frm) {
        if (frm.doc.all_client_scripts) {
            if (frm.fields_dict['export_client_scripts']) {
                frm.set_df_property('export_client_scripts', 'read_only', 1);
                frm.set_value('export_client_scripts', []);
            }
        } else {
            if (frm.fields_dict['export_client_scripts']) {
                frm.set_df_property('export_client_scripts', 'read_only', 0);
            }
        }
        frm.refresh_field('export_client_scripts');
    },
    
    all_server_scripts: function(frm) {
        if (frm.doc.all_server_scripts) {
            if (frm.fields_dict['export_server_scripts']) {
                frm.set_df_property('export_server_scripts', 'read_only', 1);
                frm.set_value('export_server_scripts', []);
            }
        } else {
            if (frm.fields_dict['export_server_scripts']) {
                frm.set_df_property('export_server_scripts', 'read_only', 0);
            }
        }
        frm.refresh_field('export_server_scripts');
    },
    
    start_export: function(frm) {
        // Clear any previous status
        frm.doc.export_status = 'Starting';
        frm.doc.export_message = 'Initializing export process...';
        frm.refresh();
        
        // Prepare data for server call
        let export_data = {
            export_doctypes: frm.doc.export_doctypes || [],
            export_client_scripts: frm.doc.export_client_scripts || [],
            export_server_scripts: frm.doc.export_server_scripts || [],
            all_client_scripts: frm.doc.all_client_scripts || 0,
            all_server_scripts: frm.doc.all_server_scripts || 0,
            emails: frm.doc.emails || []
        };
        
        // Create persistent dialog to show progress
        frm.export_dialog = new frappe.ui.Dialog({
            title: __('Export Customizations'),
            primary_action_label: __('Close'),
            primary_action: () => {
                frm.export_dialog.hide();
                // Stop polling when dialog is closed
                if (frm.export_interval) {
                    clearInterval(frm.export_interval);
                    frm.export_interval = null;
                }
            }
        });
        
        frm.export_dialog.show();
        frm.export_dialog.$body.html(`
            <div class="export-progress">
                <p>${__('Starting export process...')}</p>
                <div class="progress" style="height: 10px;">
                    <div class="progress-bar" role="progressbar" style="width: 10%;" aria-valuenow="10" aria-valuemin="0" aria-valuemax="100"></div>
                </div>
            </div>
        `);
        
        // Call server-side method
        frappe.call({
            method: 'export_import_app.export_import_app.doctype.export_customizations_module.export_customizations_module.export_customizations',
            args: {
                doctype_name: frm.docname,
                export_doc: JSON.stringify(export_data)
            },
            callback: function(r) {
                if (r.exc) {
                    // Show error message
                    frm.export_dialog.$body.html(`
                        <div class="alert alert-danger">
                            <p>${__('Failed to start export process.')}</p>
                            <p>${__('Error')}: ${r.exc}</p>
                        </div>
                    `);
                    return;
                }
                
                // Update dialog to show that background process has started
                frm.export_dialog.$body.html(`
                    <div class="export-progress">
                        <p>${__('Export process started in background.')}</p>
                        <p>${__('Current Status')}: <span class="status-text">${__('Starting...')}</span></p>
                        <div class="progress" style="height: 10px;">
                            <div class="progress-bar" role="progressbar" style="width: 20%;" aria-valuenow="20" aria-valuemin="0" aria-valuemax="100"></div>
                        </div>
                        <div class="mt-3">
                            <p class="small text-muted">${__('You can close this dialog and check back later. The process will continue in the background.')}</p>
                        </div>
                    </div>
                `);
                
                // Start polling for status updates
                frm.trigger('check_export_status');
            }
        });
    },
    
    //Changes to the check_export_status function to fix the dialog update issue

check_export_status: function(frm) {
    // Clear existing interval if any
    if (frm.export_interval) {
        clearInterval(frm.export_interval);
        frm.export_interval = null;
    }
    
    // Function to update status
    const updateStatus = function() {
        frappe.call({
            method: 'export_import_app.export_import_app.doctype.export_customizations_module.export_customizations_module.get_export_status',
            args: {
                doctype_name: frm.docname
            },
            callback: function(r) {
                if (r.exc || !r.message) {
                    console.error('Error checking export status:', r.exc);
                    return;
                }
                
                const status = r.message;
                const previousStatus = frm.doc.export_status;
                
                // Update form values
                frm.doc.export_status = status.export_status;
                frm.doc.export_message = status.export_message;
                frm.doc.last_export_update = status.last_export_update;
                
                // Force document reload if status changed to Completed
                if (previousStatus !== 'Completed' && status.export_status === 'Completed') {
                    // This will ensure we get the latest document state including any auto-save changes
                    setTimeout(() => {
                        frm.reload_doc();
                    }, 1000);
                } else {
                    // Otherwise just refresh the form to show updated status
                    frm.refresh();
                }
                
                // Update dialog if it exists
                if (frm.export_dialog && frm.export_dialog.$wrapper.is(':visible')) {
                    let progressPercent = 20;
                    let alertClass = 'alert-info';
                    
                    if (status.export_status === 'In Progress') {
                        // Calculate progress based on message
                        if (status.export_message.includes('Starting')) progressPercent = 20;
                        else if (status.export_message.includes('Updating hooks')) progressPercent = 40;
                        else if (status.export_message.includes('Running')) progressPercent = 60;
                        else if (status.export_message.includes('Saving')) progressPercent = 80;
                        else if (status.export_message.includes('Sending email')) progressPercent = 90;
                    } else if (status.export_status === 'Completed') {
                        progressPercent = 100;
                        alertClass = 'alert-success';
                    } else if (status.export_status === 'Failed') {
                        progressPercent = 100;
                        alertClass = 'alert-danger';
                    } else if (status.export_status === 'Completed with warnings') {
                        progressPercent = 100;
                        alertClass = 'alert-warning';
                    }
                    
                    let dialogContent = `
                        <div class="alert ${alertClass}">
                            <p><strong>${__(status.export_status)}</strong>: ${status.export_message}</p>
                        </div>
                        <div class="progress" style="height: 10px;">
                            <div class="progress-bar ${status.export_status === 'Failed' ? 'bg-danger' : ''}" 
                                role="progressbar" style="width: ${progressPercent}%;" 
                                aria-valuenow="${progressPercent}" aria-valuemin="0" aria-valuemax="100">
                            </div>
                        </div>
                    `;
                    
                    // If completed, add file links
                    if (status.completed && status.files && status.files.length) {
                        // Find the zip file if it exists
                        const zipFile = status.files.find(file => file.is_zip);
                        
                        dialogContent += `<div class="mt-3"><p><strong>${__('Exported Files')}:</strong></p>`;
                        
                        if (zipFile) {
                            dialogContent += `
                                <p><a href="${zipFile.file_url}" target="_blank" class="btn btn-sm btn-primary">
                                    <i class="fa fa-download"></i> ${__('Download All Files (ZIP)')}
                                </a></p>
                            `;
                        }
                        
                        dialogContent += '<div style="max-height: 200px; overflow-y: auto;"><ul>';
                        status.files.forEach(file => {
                            if (!file.is_zip) {
                                dialogContent += `<li><a href="${file.file_url}" target="_blank">${file.file_name}</a></li>`;
                            }
                        });
                        dialogContent += '</ul></div></div>';
                    }
                    
                    frm.export_dialog.$body.html(dialogContent);
                    
                    // Change dialog title for completed statuses
                    if (status.completed) {
                        frm.export_dialog.set_title(__(status.export_status));
                    }
                }
                
                // If process is completed, stop polling
                if (status.completed) {
                    clearInterval(frm.export_interval);
                    frm.export_interval = null;
                    
                    // Auto-close the dialog after 30 seconds if completed
                    if (status.export_status === 'Completed' && frm.export_dialog && frm.export_dialog.$wrapper.is(':visible')) {
                        setTimeout(() => {
                            // Only close if still visible and status is still completed
                            if (frm.export_dialog && frm.export_dialog.$wrapper.is(':visible') && 
                                frm.doc.export_status === 'Completed') {
                                frm.export_dialog.hide();
                            }
                        }, 30000); // 30 seconds
                    }
                    
                    // If completed successfully and dialog is not showing, show a summary
                    if (status.export_status === 'Completed' && 
                        (!frm.export_dialog || !frm.export_dialog.$wrapper.is(':visible')) &&
                        status.files && status.files.length) {
                        
                        showExportSummary(frm, status.files);
                    }
                }
            }
        });
    };
    
    // Update immediately
    updateStatus();
    
    // Set interval to update every 3 seconds (reduced from 5 seconds for faster feedback)
    frm.export_interval = setInterval(updateStatus, 3000);
},

// Modified start_export function to use a persistent dialog
start_export: function(frm) {
    // Clear any previous status
    frm.doc.export_status = 'Starting';
    frm.doc.export_message = 'Initializing export process...';
    frm.refresh();
    
    // Prepare data for server call
    let export_data = {
        export_doctypes: frm.doc.export_doctypes || [],
        export_client_scripts: frm.doc.export_client_scripts || [],
        export_server_scripts: frm.doc.export_server_scripts || [],
        all_client_scripts: frm.doc.all_client_scripts || 0,
        all_server_scripts: frm.doc.all_server_scripts || 0,
        emails: frm.doc.emails || []
    };
    
    // Create persistent dialog to show progress
    frm.export_dialog = new frappe.ui.Dialog({
        title: __('Export Customizations'),
        primary_action_label: __('Close'),
        primary_action: () => {
            frm.export_dialog.hide();
            // Stop polling when dialog is closed
            if (frm.export_interval) {
                clearInterval(frm.export_interval);
                frm.export_interval = null;
            }
        }
    });
    
    frm.export_dialog.show();
    frm.export_dialog.$body.html(`
        <div class="export-progress">
            <p>${__('Starting export process...')}</p>
            <div class="progress" style="height: 10px;">
                <div class="progress-bar" role="progressbar" style="width: 10%;" aria-valuenow="10" aria-valuemin="0" aria-valuemax="100"></div>
            </div>
            <div class="alert alert-info mt-3">
                <p><i class="fa fa-info-circle"></i> ${__('The export is running in the background. You can close this dialog and continue working.')}</p>
            </div>
        </div>
    `);
    
    // Call server-side method
    frappe.call({
        method: 'export_import_app.export_import_app.doctype.export_customizations_module.export_customizations_module.export_customizations',
        args: {
            doctype_name: frm.docname,
            export_doc: JSON.stringify(export_data)
        },
        callback: function(r) {
            if (r.exc) {
                // Show error message
                frm.export_dialog.$body.html(`
                    <div class="alert alert-danger">
                        <p>${__('Failed to start export process.')}</p>
                        <p>${__('Error')}: ${r.exc}</p>
                    </div>
                `);
                return;
            }
            
            // Update dialog to show that background process has started
            frm.export_dialog.$body.html(`
                <div class="export-progress">
                    <p>${__('Export process started in background.')}</p>
                    <p>${__('Current Status')}: <span class="status-text">${__('Starting...')}</span></p>
                    <div class="progress" style="height: 10px;">
                        <div class="progress-bar" role="progressbar" style="width: 20%;" aria-valuenow="20" aria-valuemin="0" aria-valuemax="100"></div>
                    </div>
                    <div class="alert alert-info mt-3">
                        <p><i class="fa fa-info-circle"></i> ${__('The export is running in the background. You can close this dialog and continue working.')}</p>
                        <p>${__('Status is refreshed automatically every 3 seconds.')}</p>
                    </div>
                </div>
            `);
            
            // Start polling for status updates with a small delay to give the background job time to start
            setTimeout(() => {
                frm.trigger('check_export_status');
            }, 1000);
        }
    });
}
});

// Function to show export summary in a dialog
function showExportSummary(frm, files) {
    const zipFile = files.find(file => file.is_zip);
    
    let content = `<div class="alert alert-success">
        <p>${__('Export completed successfully!')}</p>
    </div>`;
    
    if (zipFile) {
        content += `
            <p><a href="${zipFile.file_url}" target="_blank" class="btn btn-primary">
                <i class="fa fa-download"></i> ${__('Download All Files (ZIP)')}
            </a></p>
        `;
    }
    
    content += `<p><strong>${__('Exported Files')}:</strong></p>`;
    content += '<div style="max-height: 300px; overflow-y: auto;"><ul>';
    
    files.forEach(file => {
        if (!file.is_zip) {
            content += `<li><a href="${file.file_url}" target="_blank">${file.file_name}</a></li>`;
        }
    });
    
    content += '</ul></div>';
    
    // Create and show dialog
    const d = new frappe.ui.Dialog({
        title: __('Export Summary'),
        fields: [{
            fieldtype: 'HTML',
            options: content
        }],
        primary_action_label: __('OK'),
        primary_action: () => d.hide()
    });
    
    d.show();
}