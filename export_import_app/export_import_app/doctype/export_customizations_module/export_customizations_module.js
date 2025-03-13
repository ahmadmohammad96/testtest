// Copyright (c) 2025, ahmadmohammad96 and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Export Customizations Module", {
// 	refresh(frm) {

// 	},
// });




// Client Script for Export Customizations Module
frappe.ui.form.on('Export Customizations Module', {
    refresh: function(frm) {
        // Add button to export customizations
        frm.add_custom_button(__('Export Customizations'), function() {
            frappe.show_alert({
                message: __('Exporting customizations, please wait...'),
                indicator: 'blue'
            });
            
            frappe.call({
                method: 'export_import_app.export_import_app.doctype.export_customizations_module.export_customizations_module.export_customizations',
                args: {
                    doc_name: frm.doc.name
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.show_alert({
                            message: __('Customizations exported successfully. File ID: ' + r.message),
                            indicator: 'green'
                        });
                    }
                }
            });
        }, __('Actions'));
        
        // Add button to send email with exported customizations
        frm.add_custom_button(__('Send Export Via Email'), function() {
            frappe.confirm(
                'This will send the exported customizations to all emails in the list. Continue?',
                function() {
                    frappe.show_alert({
                        message: __('Sending emails, please wait...'),
                        indicator: 'blue'
                    });
                    
                    frappe.call({
                        method: 'export_import_app.export_import_app.doctype.export_customizations_module.export_customizations_module.send_customization_email',
                        args: {
                            doc_name: frm.doc.name
                        },
                        callback: function(r) {
                            if (r.message) {
                                frappe.show_alert({
                                    message: __('Customization file sent to all specified emails.'),
                                    indicator: 'green'
                                });
                            }
                        }
                    });
                }
            );
        }, __('Actions'));
    },
    
    validate: function(frm) {
        // Validate that at least one doctype or script is selected for export
        let has_selection = false;
        
        if (frm.doc.export_doctypes && frm.doc.export_doctypes.length > 0) {
            has_selection = true;
        }
        
        if (frm.doc.all_client_scripts || 
            (frm.doc.export_client_scripts && frm.doc.export_client_scripts.length > 0)) {
            has_selection = true;
        }
        
        if (frm.doc.all_server_scripts || 
            (frm.doc.export_server_scripts && frm.doc.export_server_scripts.length > 0)) {
            has_selection = true;
        }
        
        if (!has_selection) {
            frappe.validated = false;
            frappe.throw(__('Please select at least one DocType or Script to export'));
        }
    }
});