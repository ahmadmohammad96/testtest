// Copyright (c) 2025, ahmadmohammad96 and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Import Customizations UI", {
// 	refresh(frm) {

// 	},
// });
// Client Script for Import Customizations UI
frappe.ui.form.on('Import Customizations UI', {
    refresh: function(frm) {
        // Add button to import customizations
        frm.add_custom_button(__('Import Customizations'), function() {
            if (!frm.doc.json_file) {
                frappe.msgprint(__('Please attach a customization JSON file first.'));
                return;
            }
            
            frappe.confirm(
                'This will import all customizations from the attached file. This may overwrite existing customizations. Continue?',
                function() {
                    frappe.show_alert({
                        message: __('Importing customizations, please wait...'),
                        indicator: 'blue'
                    });
                    
                    frappe.call({
                        method: 'export_import_app.export_import_app.doctype.import_customizations_ui.import_customizations_ui.import_customizations',
                        args: {
                            doc_name: frm.doc.name
                        },
                        callback: function(r) {
                            if (r.message) {
                                frappe.show_alert({
                                    message: __('Customizations imported successfully.'),
                                    indicator: 'green'
                                });
                                
                                // Show detailed summary in a dialog
                                frappe.msgprint({
                                    title: __('Import Summary'),
                                    indicator: 'green',
                                    message: r.message
                                });
                            }
                        }
                    });
                }
            );
        }, __('Actions'));
    }
});