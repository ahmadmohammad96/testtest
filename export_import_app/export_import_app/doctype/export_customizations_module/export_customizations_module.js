// Copyright (c) 2025, ahmadmohammad96 and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Export Customizations Module", {
// 	refresh(frm) {

// 	},
// });
// Copyright (c) 2023, Your Name and contributors
// For license information, please see license.txt
// Copyright (c) 2025, ahmadmohammad96 and contributors
// For license information, please see license.txt
// Copyright (c) 2025, ahmadmohammad96 and contributors
// For license information, please see license.txt

frappe.ui.form.on('Export Customizations Module', {
    refresh: function(frm) {
        // Initialize export status if not set
        if (!frm.doc.export_status) {
            frm.doc.export_status = "Not Started";
            frm.doc.export_message = "Ready to export";
            frm.doc.last_export_update = frappe.datetime.now_datetime();
            frm.refresh_field('export_status');
            frm.refresh_field('export_message');
            frm.refresh_field('last_export_update');
        }
        
        // Robust check for saved document - checking both is_new and creation
        const isSaved = !frm.is_new() && frm.doc.creation && frm.doc.name !== "new-export-customizations-module";
        
        if (isSaved) {
            // Only add export button if definitely saved
            frm.add_custom_button(__('Export Customizations'), function() {
                // Show a confirmation dialog
                frappe.confirm(
                    __('Are you sure you want to export the selected customizations?'),
                    function() {
                        // Yes callback - directly call export function since doc is already saved
                        frm.call({
                            method: 'export_import_app.export_import_app.doctype.export_customizations_module.export_customizations_module.export_customizations',
                            args: {
                                docname: frm.doc.name
                            },
                            freeze: true,
                            freeze_message: __('Exporting customizations...'),
                            callback: function(r) {
                                // Refresh the form to show updated status
                                frm.reload_doc();
                            }
                        });
                    },
                    function() {
                        // No callback - do nothing
                    }
                );
            }).addClass('btn-primary');
        } else {
            // Show a message that document needs to be saved first
            frm.set_intro(__('Please save this document first before exporting customizations.'), 'yellow');
            
            // Clear any old buttons to prevent issues
            frm.remove_custom_button(__('Export Customizations'));
        }
        
        // Add a button to download the last export file if it exists
        if (frm.doc.last_export_file) {
            frm.add_custom_button(__('Download Last Export'), function() {
                window.open('/api/method/frappe.utils.file_manager.download_file?file_url=' + encodeURIComponent(frm.doc.last_export_file));
            }).addClass('btn-info');
        }
        
        // Toggle visibility of client scripts selection based on "All Client Scripts" checkbox
        frm.toggle_display('export_client_scripts', !frm.doc.all_client_scripts);
        
        // Toggle visibility of server scripts selection based on "All Server Scripts" checkbox
        frm.toggle_display('export_server_scripts', !frm.doc.all_server_scripts);
        
        // Set indicator color based on export status
        set_status_indicator(frm);
    },
    
    all_client_scripts: function(frm) {
        // Toggle visibility of client scripts selection when the checkbox is changed
        frm.toggle_display('export_client_scripts', !frm.doc.all_client_scripts);
    },
    
    all_server_scripts: function(frm) {
        // Toggle visibility of server scripts selection when the checkbox is changed
        frm.toggle_display('export_server_scripts', !frm.doc.all_server_scripts);
    },
    
    after_save: function(frm) {
        // Refresh the form after save to update the button states
        frm.reload_doc();
    },
    
    validate: function(frm) {
        // Validate if at least one item is selected for export
        let has_selection = false;
        
        if (frm.doc.export_doctypes && frm.doc.export_doctypes.length > 0) {
            has_selection = true;
        } else if (frm.doc.all_client_scripts) {
            has_selection = true;
        } else if (frm.doc.export_client_scripts && frm.doc.export_client_scripts.length > 0) {
            has_selection = true;
        } else if (frm.doc.all_server_scripts) {
            has_selection = true;
        } else if (frm.doc.export_server_scripts && frm.doc.export_server_scripts.length > 0) {
            has_selection = true;
        }
        
        if (!has_selection) {
            frappe.msgprint(__('Please select at least one doctype, client script, or server script to export.'));
            frappe.validated = false;
        }
    }
});

// Helper function to set status indicator
function set_status_indicator(frm) {
    let statusIndicator = '';
    
    switch(frm.doc.export_status) {
        case 'Not Started':
            statusIndicator = 'gray';
            break;
        case 'Starting':
            statusIndicator = 'blue';
            break;
        case 'In Progress':
            statusIndicator = 'orange';
            break;
        case 'Completed':
            statusIndicator = 'green';
            break;
        case 'Completed with warnings':
            statusIndicator = 'yellow';
            break;
        case 'Failed':
            statusIndicator = 'red';
            break;
        default:
            statusIndicator = 'gray';
    }
    
    frm.set_indicator(frm.doc.export_status, statusIndicator);
}